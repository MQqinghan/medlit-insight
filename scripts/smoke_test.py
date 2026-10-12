"""端到端冒烟测试：进程内起服务 → 打请求 → 断言 → 退出。

用法（项目根目录）：
    python scripts/smoke_test.py

特点：不依赖服务常驻（沙箱/CI 可跑）；本地请求 trust_env=False 绕开代理劫持；
真实调用 PubMed E-utilities（无 API key 时按 3 req/s 限速，故抓取量调小加速）。
"""
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("MAX_FETCH", "600")  # 冒烟加速：只抓 600 篇（3 批），代码路径与默认 2000 一致

import httpx  # noqa: E402
import uvicorn  # noqa: E402

from app.main import app  # noqa: E402

HOST, PORT = "127.0.0.1", 8765
BASE = f"http://{HOST}:{PORT}"
passed, failed = [], []


def check(name, ok, detail=""):
    (passed if ok else failed).append(f"{name} {detail}".strip())
    print(("  PASS " if ok else "  FAIL ") + name + (f"  [{detail}]" if detail else ""))


def serve():
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def main():
    th = threading.Thread(target=serve, daemon=True)
    th.start()
    time.sleep(3.0)
    result = None
    try:
        with httpx.Client(base_url=BASE, timeout=httpx.Timeout(300.0, connect=10.0), trust_env=False) as c:
            # 1) 健康检查
            r = c.get("/api/health")
            h = r.json()
            check("health", r.status_code == 200 and h.get("ok"), json.dumps(h, ensure_ascii=False))

            # 2) 首页与静态资源
            r = c.get("/")
            check("index", r.status_code == 200 and "文献罗盘" in r.text, f"{r.status_code}")
            for p in ("/static/js/app.js", "/static/vendor/vue.global.prod.js", "/static/vendor/echarts.min.js"):
                r = c.get(p)
                check(f"static {p}", r.status_code == 200, f"{r.status_code}")

            # 3) SSE 全链路（真实 PubMed；force=1 绕过缓存，保证验证完整流水线）
            stages = []
            with c.stream("GET", "/api/analyze/stream", params={"q": "diabetic retinopathy", "years": 5, "force": 1}) as r:
                check("sse status", r.status_code == 200, f"{r.status_code}")
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    d = json.loads(line[5:].strip())
                    stages.append(d["stage"])
                    if d["stage"] == "error":
                        check("sse chain", False, d.get("message", ""))
                        break
                    if d["stage"] == "done":
                        result = d["result"]
            check("sse stages", all(s in stages for s in ("search", "search_recent", "trend", "fetch", "analyze", "review", "done")),
                  "→".join(stages))
            check("fetch progress", stages.count("fetch") >= 3, f"{stages.count('fetch')} batches")

            if result:
                s = result["stats"]
                check("total_count > 0", s["total_count"] > 0, str(s["total_count"]))
                check("recent_count > 0", s["recent_count"] > 0, str(s["recent_count"]))
                check("analyzed_count", s["analyzed_count"] > 100, str(s["analyzed_count"]))
                check("year_trend 10y", len(s.get("year_trend", {})) == 10)
                check("journal_top", len(s["journal_top"]) > 0)
                check("zone_dist keys", set(s["zone_dist"]) == {"1", "2", "3", "4", "none"})
                check("wordcloud", len(result["wordcloud"]) > 20, f"{len(result['wordcloud'])} words")
                check("top100 list", 0 < len(s["top_n"]) <= 100, f"{len(s['top_n'])} 条")
                t1 = s["top_n"][0]
                check("top1 has if/journal", t1.get("if") is not None and bool(t1.get("journal")), f'{t1.get("journal")} IF {t1.get("if")}')
                check("review fallback", result["review"]["source"] == "fallback", "沙箱无 LLM key，应走兜底")
                check("review length", 300 <= len(result["review"]["markdown"]) <= 1200,
                      f'{len(result["review"]["markdown"])} 字')

                # 4) 导出
                r = c.post("/api/export/md", json=result)
                check("export md", r.status_code == 200 and "# 文献洞察报告" in r.text, f"{r.status_code}")
                r = c.post("/api/export/docx", json=result)
                check("export docx", r.status_code == 200 and r.content[:2] == b"PK", f"{r.status_code}, {len(r.content)}B")

                # 5) 缓存命中（第二次同一查询应立即 done 且 cache_hit）
                t0 = time.monotonic()
                hit = None
                with c.stream("GET", "/api/analyze/stream", params={"q": "diabetic retinopathy", "years": 5}) as r:
                    for line in r.iter_lines():
                        if line.startswith("data:"):
                            d = json.loads(line[5:].strip())
                            if d["stage"] == "done":
                                hit = d.get("cache_hit")
                check("cache hit", hit is True, f"{time.monotonic() - t0:.2f}s")
    except Exception:
        import traceback
        traceback.print_exc()
        failed.append("exception")
    finally:
        print(f"\n===== {len(passed)} passed, {len(failed)} failed =====")
        if failed:
            print("FAILED:", *failed, sep="\n  - ")
        sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
