"""PubMed E-utilities 异步客户端。

限速策略（NCBI 官方口径）：无 API key 3 req/s，有 key 10 req/s。
实现 = 信号量（并发上限）+ 令牌间隔（请求间最小间隔）+ 指数退避重试，
双保险避免 429 被临时封 IP。
"""
import asyncio
import random
import time

import httpx

from . import config
from .parser import parse_pubmed_xml

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedError(Exception):
    pass


class PubMedClient:
    def __init__(self):
        self.api_key = config.get("PUBMED_API_KEY")
        self._sem = asyncio.Semaphore(8)
        self._rate_lock = asyncio.Lock()
        self._last_req = 0.0
        # 保守取值：有 key 8 req/s，无 key 2.5 req/s
        self._min_interval = 0.12 if self.api_key else 0.4
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"User-Agent": f'{config.get("PUBMED_TOOL")}/1.0 (mailto:{config.get("PUBMED_EMAIL")})'},
        )

    async def aclose(self):
        await self._client.aclose()

    def _params(self, extra):
        p = {
            "tool": config.get("PUBMED_TOOL"),
            "email": config.get("PUBMED_EMAIL"),
        }
        if self.api_key:
            p["api_key"] = self.api_key
        p.update(extra)
        return p

    async def _get(self, path, params, retries=3):
        url = f"{EUTILS_BASE}/{path}"
        last_err = None
        for attempt in range(retries):
            async with self._sem:
                # 令牌间隔：两次请求启动至少间隔 _min_interval
                async with self._rate_lock:
                    wait = self._min_interval - (time.monotonic() - self._last_req)
                    if wait > 0:
                        await asyncio.sleep(wait)
                    self._last_req = time.monotonic()
                try:
                    r = await self._client.get(url, params=self._params(params))
                    if r.status_code == 429 or r.status_code >= 500:
                        last_err = PubMedError(f"HTTP {r.status_code}")
                        await asyncio.sleep((2 ** attempt) + random.uniform(0, 0.3))
                        continue
                    r.raise_for_status()
                    return r
                except httpx.HTTPError as e:
                    last_err = PubMedError(str(e))
                    await asyncio.sleep((2 ** attempt) + random.uniform(0, 0.3))
        raise PubMedError(f"E-utilities 请求失败（重试 {retries} 次后仍失败）: {last_err}")

    # ---------------- ESearch ----------------
    async def search(self, term, retmax=0, sort=None):
        """返回 {count, ids, webenv, query_key}。retmax=0 表示只要 count。"""
        params = {"db": "pubmed", "term": term, "retmode": "json", "usehistory": "y"}
        if retmax:
            params["retmax"] = min(int(retmax), 10000)
        if sort:
            params["sort"] = sort
        r = await self._get("esearch.fcgi", params)
        try:
            res = r.json()["esearchresult"]
        except Exception as e:
            raise PubMedError(f"ESearch 返回解析失败: {e}")
        return {
            "count": int(res.get("count", 0)),
            "ids": res.get("idlist", []),
            "webenv": res.get("webenv", ""),
            "query_key": res.get("querykey", ""),
        }

    # ---------------- EFetch ----------------
    async def fetch_batch(self, ids):
        params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}
        r = await self._get("efetch.fcgi", params)
        return parse_pubmed_xml(r.text)

    async def fetch_all(self, ids, batch_size=200, on_progress=None):
        """分批并发抓取详情。on_progress(done, total_batches) 为同步回调。"""
        batch_size = int(batch_size) or 200
        batches = [ids[i:i + batch_size] for i in range(0, len(ids), batch_size)]
        if not batches:
            return []
        done = 0
        lock = asyncio.Lock()

        async def run(batch):
            nonlocal done
            arts = await self.fetch_batch(batch)
            async with lock:
                done += 1
                if on_progress:
                    on_progress(done, len(batches))
            return arts

        results = await asyncio.gather(*[run(b) for b in batches])
        return [a for part in results for a in part]
