"""演示视频配音生成：按分镜文案调用 qwen3-tts-flash 生成中文配音，并测量每段时长。

产物（video/ 目录，已被 gitignore）：
  voice/seg_XX.wav   每段配音
  voice/timeline.json 每段时长（毫秒），供录制与合成阶段使用

用法：python scripts/make_voice.py
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx

from app import config

OUT = ROOT / "video" / "voice"
OUT.mkdir(parents=True, exist_ok=True)

TTS_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
VOICE = "Cherry"

# 分镜文案。数字一律用约数/中文读法（真实精确值由画面展示，数据每日微涨不影响配音正确性）。
# (id, 文案)
SEGMENTS = [
    ("00_intro", "文献罗盘，一个面向医生的PubMed文献洞察工具。输入一个研究方向，三十秒内看清这个领域的规模、热点与顶尖文献，并生成一份中文综述。"),
    ("01_search", "我们以糖尿病视网膜病变为例。输入关键词，点击开始分析。后端调用PubMed官方接口，界面实时展示每个阶段的进度：检索、统计年度趋势、抓取文献详情、匹配期刊指标，最后生成综述。全过程视网络情况约一到三分钟，这里加速播放。"),
    ("02_kpi", "结果出来了。该领域累计文献五万三千余篇，近五年一万三千余篇，占比约四分之一，仍处于活跃期。年度趋势显示发文量在二零二三年达到峰值。样本中位影响因子为五，一区期刊占比百分之三，规模庞大，但高影响力成果相对集中。"),
    ("03_cloud", "词云基于MeSH主题词词频生成，快速定位研究热点：人工智能筛查、抗VEGF治疗、血糖控制是最活跃的方向。期刊格局方面，成果主要发表在眼科与综合医学期刊，分区以二区、三区为主体。"),
    ("04_top", "影响力榜单取近五年样本内影响因子排名前一百的文献。需要说明的是，影响因子与分区数据来自本地静态期刊库，PubMed本身不提供这两个字段，页面已明确标注数据口径。榜首是临床研究期刊，影响因子接近十六。"),
    ("05_review", "最后是基于入选文献摘要生成的中文综述，由通义千问大模型撰写，约六百字，分五个要点：研究现状、主要研究方向、方法学趋势、代表性发现、空白与展望。所有数字都锚定真实检索结果。如果大模型服务不可用，系统会自动切换到统计模板兜底，保证任何情况下都有输出。"),
    ("06_outro", "报告支持导出Markdown、Word和PDF。本项目由AI编程工具协作完成，从需求到上线，七类典型错误的发现与修正过程都记录在仓库协作文档中。感谢观看。"),
]

FFMPEG = None  # 延迟导入，避免未装依赖时脚本开头就挂


def get_ffmpeg():
    global FFMPEG
    if FFMPEG is None:
        import imageio_ffmpeg
        FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
    return FFMPEG


def tts(text: str, out: Path):
    """调用 qwen3-tts-flash 合成并下载音频。"""
    key = config.get("LLM_API_KEY")
    r = httpx.post(
        TTS_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "qwen3-tts-flash", "input": {"text": text, "voice": VOICE, "language_type": "Chinese"}},
        timeout=120,
        trust_env=False,
    )
    r.raise_for_status()
    url = r.json()["output"]["audio"]["url"]
    audio = httpx.get(url, timeout=60, trust_env=False)
    audio.raise_for_status()
    out.write_bytes(audio.content)


def duration_ms(path: Path) -> int:
    """用 ffmpeg 探测音频时长（毫秒）。"""
    exe = get_ffmpeg()
    # ffmpeg -i 输出到 stderr；用 -f null 解码一遍拿准确时长
    p = subprocess.run(
        [exe, "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    line = [l for l in p.stderr.splitlines() if "Duration" in l]
    if not line:
        raise RuntimeError(f"无法解析时长: {path}")
    # 形如 Duration: 00:00:12.34, start: ...
    ts = line[0].split("Duration:")[1].split(",")[0].strip()
    h, m, s = ts.split(":")
    return int(round((int(h) * 3600 + int(m) * 60 + float(s)) * 1000))


def main():
    timeline = {}
    for i, (sid, text) in enumerate(SEGMENTS, 1):
        out = OUT / f"seg_{i:02d}_{sid}.wav"
        if not out.exists():
            print(f"[{i}/{len(SEGMENTS)}] {sid} 生成中（{len(text)} 字）…")
            tts(text, out)
            time.sleep(0.5)  # 轻微限速，避免触发风控
        ms = duration_ms(out)
        timeline[sid] = {"file": out.name, "duration_ms": ms, "text": text}
        print(f"  {sid}: {ms/1000:.1f}s  ({out.stat().st_size//1024} KB)")
    (OUT / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(v["duration_ms"] for v in timeline.values())
    print(f"\n配音总时长: {total/1000:.1f}s（不含画面停留与过渡）")


if __name__ == "__main__":
    main()
