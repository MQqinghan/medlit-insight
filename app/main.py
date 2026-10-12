"""FastAPI 入口：SSE 流式分析 + 导出接口 + 静态页面。"""
import asyncio
import json
import os
import time
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .analysis import build_stats, build_wordcloud, current_year, enrich_with_journal
from .cache import get as cache_get, make_key, set as cache_set
from .export import DOCX_AVAILABLE, build_docx, build_markdown
from .journals import JournalDB
from .llm import generate_review
from .pubmed import PubMedClient, PubMedError

app = FastAPI(title="medlit-insight", version="0.1.0")

STATIC_DIR = os.path.join(config.BASE_DIR, "app", "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_jdb = JournalDB()


@app.get("/", response_class=None)
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "pubmed_key": bool(config.get("PUBMED_API_KEY")),
        "llm_key": bool(config.get("LLM_API_KEY")),
        "docx_export": DOCX_AVAILABLE,
        "journal_db_version": _jdb.version,
        "journal_db_size": len(_jdb._by_issn),
    }


@app.get("/api/analyze/stream")
async def analyze_stream(q: str, years: int = 0, force: int = 0):
    """SSE：search → search_recent → trend → fetch → analyze → review → done"""
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(stage, **kw):
        await queue.put({"stage": stage, **kw})

    async def worker():
        client = PubMedClient()
        t0 = time.monotonic()
        try:
            keyword = q.strip()
            if not keyword:
                raise ValueError("关键词不能为空")
            # 注意：worker 内不能再给 years 赋值（会遮蔽外层参数导致 UnboundLocalError），故用 years_n
            years_n = min(max(int(years or config.get("REVIEW_YEARS")), 1), 10)
            max_fetch = min(int(config.get("MAX_FETCH")), 5000)
            batch = int(config.get("FETCH_BATCH"))
            top_n = int(config.get("TOP_N"))
            cy = current_year()
            start_year = cy - years_n + 1

            cache_key = make_key(keyword, years_n, max_fetch, top_n, _jdb.version)
            if not force:
                cached = cache_get(cache_key)
                if cached:
                    cached.setdefault("meta", {})["cache_hit"] = True
                    await emit("done", result=cached, cache_hit=True)
                    return

            # 1) 全时段命中总量
            total = await client.search(keyword, retmax=0)
            await emit("search", keyword=keyword, total_count=total["count"])

            # 2) 近N年集合：一次拿 count + 前 max_fetch 个 PMID
            recent_term = f"{keyword} AND {start_year}:{cy}[dp]"
            recent = await client.search(recent_term, retmax=max_fetch)
            await emit("search_recent", recent_count=recent["count"],
                       start_year=start_year, end_year=cy, will_fetch=min(len(recent["ids"]), max_fetch))

            # 3) 近10年逐年精确计数（趋势图，不受采样偏差影响）
            trend_years = int(config.get("TREND_YEARS"))
            year_counts = {}
            for y in range(cy - trend_years + 1, cy + 1):
                r = await client.search(f"{keyword} AND {y}[dp]", retmax=0)
                year_counts[str(y)] = r["count"]
            await emit("trend", year_counts=year_counts)

            # 4) 抓取近N年样本详情（分批并发 + 进度回调）
            ids = recent["ids"][:max_fetch]

            def on_prog(done, n_batches):
                asyncio.ensure_future(emit(
                    "fetch", done=done, total=n_batches,
                    fetched=min(done * batch, len(ids)),
                ))

            articles = await client.fetch_all(ids, batch_size=batch, on_progress=on_prog)
            if not articles:
                raise PubMedError(f"未抓取到文献详情（近{years_n}年命中 {recent['count']} 篇）")

            # 5) 分析
            enriched = enrich_with_journal(articles, _jdb)
            wordcloud = build_wordcloud(enriched)
            stats = build_stats(enriched, total["count"], recent["count"], top_n=top_n, review_years=years_n)
            stats["year_trend"] = year_counts
            stats["mesh_top"] = wordcloud[:10]
            await emit("analyze", analyzed_count=stats["analyzed_count"],
                       matched_ratio=stats["matched_ratio"])

            # 6) LLM 综述（失败自动兜底）
            await emit("review")
            review_md, source = await generate_review(keyword, stats, stats["top_n"])

            result = {
                "keyword": keyword,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "params": {"years": years_n, "max_fetch": max_fetch,
                           "start_year": start_year, "end_year": cy, "top_n": top_n},
                "stats": stats,
                "wordcloud": wordcloud,
                "review": {"markdown": review_md, "source": source,
                           "model": config.get("LLM_MODEL") if source == "llm" else None},
                "meta": {
                    "journal_db_version": _jdb.version,
                    "elapsed_ms": int((time.monotonic() - t0) * 1000),
                    "cache_hit": False,
                },
            }
            cache_set(cache_key, result)
            await emit("done", result=result, cache_hit=False)
        except Exception as e:
            await emit("error", message=str(e) or e.__class__.__name__)
        finally:
            await client.aclose()

    async def gen():
        task = asyncio.ensure_future(worker())
        try:
            while True:
                item = await queue.get()
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                if item["stage"] in ("done", "error"):
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/export/md")
async def export_md(payload: dict):
    md = build_markdown(payload)
    name = f'文献洞察_{payload.get("keyword", "report")}.md'
    return Response(
        content=md.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{_quote(name)}"},
    )


@app.post("/api/export/docx")
async def export_docx(payload: dict):
    if not DOCX_AVAILABLE:
        return JSONResponse(status_code=500, content={"detail": "python-docx 未安装"})
    try:
        data = build_docx(payload)
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"docx 生成失败: {e}"})
    name = f'文献洞察_{payload.get("keyword", "report")}.docx'
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{_quote(name)}"},
    )


def _quote(name):
    from urllib.parse import quote
    return quote(name)
