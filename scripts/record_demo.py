"""演示视频录制：进程内起 demo 服务 → Playwright 驱动 Edge 按分镜操作并录屏 → 输出 markers.json。

用法（项目根目录）：
    python scripts/record_demo.py

产物（video/ 目录）：
  raw/recording.webm   浏览器录屏（无声）
  raw/markers.json     各镜头在录像中的墙钟时刻（毫秒），供 compose_video.py 剪辑
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
# 注意：不再注入 MAX_FETCH=600 压样本——视频必须与正式运行同参（默认 2000），
# 否则 Top100 只出 75 条，与笔试"影响力前 100"口径冲突（2026-10-15 审片发现）。

import uvicorn  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from app.main import app  # noqa: E402

HOST, PORT = "127.0.0.1", 8000
BASE = f"http://{HOST}:{PORT}"
OUT = ROOT / "video" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

KEYWORD = "diabetic retinopathy"

# 分镜停留时长（秒）：录制时画面停留多久（配音时长见 make_voice.py，留 1-2s 余量）
DWELL = {
    "card_open": 16,      # 片头卡（配音 14.2s）
    "type_click": 8,      # 打字 + 点击（配音 01 前段）
    "kpi": 26,            # KPI + 趋势（配音 23.8s）
    "cloud": 12,          # 词云 + 年度趋势（配音 03 前半）
    "journals": 10,       # 期刊 Top10 + 分区分布（配音 03 后半）
    "top": 25,            # Top100 表（配音 22.4s）
    "review": 28,         # 综述卡（配音 25.7s）
    "export": 6,          # 导出点击
    "card_end": 16,       # 片尾卡（配音 14.6s）
}

FAKE_CURSOR_JS = """
(cfg) => {
  let cur = document.getElementById('fake-cursor');
  if (!cur) {
    cur = document.createElement('div');
    cur.id = 'fake-cursor';
    cur.style.cssText = 'position:fixed;left:0;top:0;width:20px;height:20px;border-radius:50%;'
      + 'background:#ef4444;border:2px solid #fff;box-shadow:0 1px 6px rgba(0,0,0,.45);'
      + 'z-index:2147483647;pointer-events:none;';
    document.body.appendChild(cur);
  }
  const r = cur.getBoundingClientRect();
  cur.style.left = (cfg.x - 10) + 'px';
  cur.style.top = (cfg.y - 10) + 'px';
}
"""


def move_cursor(page, selector=None, x=None, y=None):
    """把假光标移到元素中心或指定坐标。"""
    if selector:
        box = page.locator(selector).first.bounding_box()
        if not box:
            return
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.evaluate(FAKE_CURSOR_JS, {"x": x, "y": y})


def scroll_to(page, js_element_expr):
    """平滑滚动到锚点（传入返回 DOM 元素的 JS 表达式），等待滚动稳定。"""
    page.evaluate(f"({js_element_expr}).scrollIntoView({{behavior:'smooth', block:'start'}})")
    page.wait_for_timeout(1200)


def main():
    # 0) 清缓存 + 清旧录像（否则"取最大文件"启发式可能选到上一轮的旧录像）
    cache = ROOT / "cache"
    if cache.exists():
        for f in cache.glob("*.json"):
            f.unlink()
        print("cache cleared")
    raw_dir = ROOT / "video" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for f in raw_dir.glob("*.webm"):
        f.unlink()
    print("old recordings cleared")

    # 1) 进程内起服务（与 smoke_test.py 同模式，沙箱可收尾）
    th = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": HOST, "port": PORT, "log_level": "warning"},
        daemon=True,
    )
    th.start()
    time.sleep(3)
    print(f"server up at {BASE}")

    markers = {}
    t0 = time.monotonic()

    def mark(name):
        markers[name] = int((time.monotonic() - t0) * 1000)
        print(f"  [{markers[name]/1000:7.2f}s] {name}")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(OUT),
            record_video_size={"width": 1920, "height": 1080},
            accept_downloads=True,
        )
        page = ctx.new_page()

        # 2) 片头卡
        card_open = (ROOT / "video" / "assets" / "card_open.html").as_uri()
        page.goto(card_open)
        page.wait_for_timeout(1500)
        mark("start")
        page.wait_for_timeout(int(DWELL["card_open"] * 1000) - 1500)

        # 3) demo 首页：打字 + 点击检索
        page.goto(BASE)
        page.wait_for_selector(".search-card input:not([type=checkbox])", timeout=30000)
        page.wait_for_timeout(1200)
        move_cursor(page, ".search-card input:not([type=checkbox])")
        page.wait_for_timeout(600)
        page.locator(".search-card input:not([type=checkbox])").press_sequentially(KEYWORD, delay=140)
        page.wait_for_timeout(1500)
        move_cursor(page, ".search-card button.primary")
        page.wait_for_timeout(700)
        mark("type_click")
        page.locator(".search-card button.primary").click()
        mark("search_start")

        # 4) 等结果（真实全链路，约 1 分钟）
        page.wait_for_selector(".kpi-grid", timeout=300000)
        mark("result_ready")
        page.wait_for_timeout(2000)

        # 5) 分镜滚动 + 停留
        scroll_to(page, "document.querySelector('.kpi-grid')")
        mark("kpi")
        page.wait_for_timeout(int(DWELL["kpi"] * 1000) - 1200)

        scroll_to(page, "document.querySelectorAll('.grid-2')[0]")
        mark("cloud")
        page.wait_for_timeout(int(DWELL["cloud"] * 1000) - 1200)

        scroll_to(page, "document.querySelectorAll('.grid-2')[1]")
        mark("journals")
        page.wait_for_timeout(int(DWELL["journals"] * 1000) - 1200)

        scroll_to(page, "document.querySelector('.table-wrap').closest('section')")
        mark("top")
        page.wait_for_timeout(int(DWELL["top"] * 1000) - 1200)

        scroll_to(page, "document.querySelector('.report-card')")
        mark("review")
        page.wait_for_timeout(int(DWELL["review"] * 1000) - 1200)

        # 6) 导出演示（点击 Markdown 导出，静默下载）
        move_cursor(page, "text=导出 Markdown")
        page.wait_for_timeout(800)
        with page.expect_download(timeout=15000) as dl_info:
            page.locator("text=导出 Markdown").first.click()
        dl_info.value.path  # 等下载落地
        mark("export")
        page.wait_for_timeout(int(DWELL["export"] * 1000) - 800)

        # 7) 片尾卡
        card_end = (ROOT / "video" / "assets" / "card_end.html").as_uri()
        page.goto(card_end)
        page.wait_for_timeout(1500)
        mark("card_end_start")
        page.wait_for_timeout(int(DWELL["card_end"] * 1000) - 1500)
        mark("end")

        # 8) 收尾：关闭页面让 video 落盘
        page.close()
        ctx.close()
        browser.close()

    video = OUT / "recording.webm"
    if not video.exists():
        # playwright 的 page.goto 会把录像切分成多个文件，只有最大的那个是全程录像
        candidates = list(OUT.rglob("*.webm"))
        if candidates:
            video = max(candidates, key=lambda p: p.stat().st_size)
    markers["video"] = str(video)
    markers["total_ms"] = markers["end"]
    (OUT / "markers.json").write_text(json.dumps(markers, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n录制完成：{video}  ({markers['total_ms']/1000:.1f}s)")
    print("markers:", json.dumps({k: v for k, v in markers.items() if k != 'video'}, ensure_ascii=False))


if __name__ == "__main__":
    main()
