"""演示视频合成：按 markers.json 剪辑录像 + 按时间轴对齐配音 + 输出最终 mp4。

前置：先跑 scripts/record_demo.py（产 video/raw/recording.webm + markers.json）
      和 scripts/make_voice.py（产 video/voice/*.wav + timeline.json）

用法：python scripts/compose_video.py
产物：video/medlit_demo.mp4
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "video"
RAW = VIDEO_DIR / "raw"
WORK = VIDEO_DIR / "work"
WORK.mkdir(parents=True, exist_ok=True)

# 视频分段：(起始 marker, 结束 marker, 速度系数<1 为快进)
# S2 为真实检索全过程（实测 95-145s 波动），按 4 倍速呈现
SEGMENTS = [
    ("start", "type_click", 1.0),
    ("search_start", "result_ready", 0.25),
    ("result_ready", "kpi", 1.0),
    ("kpi", "cloud", 1.0),
    ("cloud", "journals", 1.0),
    ("journals", "top", 1.0),
    ("top", "review", 1.0),
    ("review", "export", 1.0),
    ("export", "card_end_start", 1.0),
    ("card_end_start", "end", 1.0),
]

# 配音放置：sid -> (所在段下标, 段内偏移秒)；None 表示绝对偏移
VOICE_PLAN = {
    "00_intro": (None, 1.0),
    "01_search": (0, -5.5),    # S1 结束前 5.5s（覆盖打字+点击）
    "02_kpi": (3, 1.5),        # S4 起点 +1.5s
    "03_cloud": (4, 1.0),      # S5 起点 +1.0s（词云+期刊共 22s，配音 19.5s）
    "04_top": (6, 1.5),        # S7 起点 +1.5s
    "05_review": (7, 1.5),     # S8 起点 +1.5s
    "06_outro": (9, 0.8),      # S10 起点 +0.8s
}

END_PAD = 1.5  # 片尾卡延长秒数（给收尾配音留空间）


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print("FFMPEG ERROR:", " ".join(cmd)[:300])
        print(p.stderr[-1500:])
        sys.exit(1)
    return p


def main():
    exe = ffmpeg()
    markers = json.loads((RAW / "markers.json").read_text(encoding="utf-8"))
    voice = json.loads((VIDEO_DIR / "voice" / "timeline.json").read_text(encoding="utf-8"))
    # playwright 的 page.goto 会把录像切分成多个文件，只有最大的那个是全程录像
    src = max(RAW.glob("*.webm"), key=lambda p: p.stat().st_size)
    print(f"源录像: {src.name}  (markers 总时长 {markers['total_ms']/1000:.1f}s)")

    # 1) 单次解码 + trim 滤镜切段变速（playwright webm 时间戳不连续，-ss seek 不可靠）
    seg_files = []
    tl = []
    pos = 0.0
    trims = []
    for i, (a, b, speed) in enumerate(SEGMENTS):
        t_a, t_b = markers[a] / 1000.0, markers[b] / 1000.0
        dur = (t_b - t_a) * speed
        if i == len(SEGMENTS) - 1:
            dur += END_PAD  # 片尾卡补时
        # trim 后重置时间戳；变速段乘速度系数
        pst = "PTS-STARTPTS" if speed == 1.0 else f"(PTS-STARTPTS)*{speed}"
        trims.append(f"[0:v]trim=start={t_a:.3f}:end={t_b:.3f},setpts={pst}[s{i}]")
        tl.append({"idx": i, "name": f"{a}->{b}", "video_start": pos, "dur": dur})
        pos += dur
    total = pos
    fc_trim = ";".join(trims)
    labels = "".join(f"[s{i}]" for i in range(len(SEGMENTS)))
    # 片尾段（最后一个）之后补静止帧
    pad_idx = len(SEGMENTS) - 1
    fc_all = fc_trim + f";[s{pad_idx}]tpad=stop_mode=clone:stop_duration={END_PAD}[s{pad_idx}p]" \
        + f";{labels.replace(f'[s{pad_idx}]', f'[s{pad_idx}p]')}" \
        + f"concat=n={len(SEGMENTS)}:v=1:a=0[vout]"
    video_only = WORK / "video_only.mp4"
    run([exe, "-y", "-i", str(src), "-filter_complex", fc_all, "-map", "[vout]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-r", "30", str(video_only)])
    print(f"剪辑后总时长: {total:.1f}s")

    # 2) 配音对位
    inputs, filters, mix_labels = [], [], []
    for j, (sid, (seg_idx, offset)) in enumerate(VOICE_PLAN.items()):
        wav = VIDEO_DIR / "voice" / voice[sid]["file"]
        if seg_idx is None:
            vpos = offset
        else:
            seg = tl[seg_idx]
            vpos = seg["video_start"] + seg["dur"] + offset if offset < 0 else seg["video_start"] + offset
        ms = int(vpos * 1000)
        inputs += ["-i", str(wav)]
        filters.append(f"[{j}:a]adelay={ms}:all=1[v{j}]")
        mix_labels.append(f"[v{j}]")
        print(f"  {sid:12s} -> {vpos:7.1f}s  (时长 {voice[sid]['duration_ms']/1000:.1f}s)")
    fc = ";".join(filters) + ";" + "".join(mix_labels) + f"amix=inputs={len(mix_labels)}:normalize=0,volume=1.0[aout]"
    voice_m4a = WORK / "voice.m4a"
    run([exe, "-y", *inputs, "-filter_complex", fc, "-map", "[aout]",
         "-c:a", "aac", "-b:a", "192k", str(voice_m4a)])

    # 3) 音视频合并
    final = VIDEO_DIR / "medlit_demo.mp4"
    run([exe, "-y", "-i", str(video_only), "-i", str(voice_m4a),
         "-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart", str(final)])

    size_mb = final.stat().st_size / 1024 / 1024
    print(f"\n✅ 成品: {final}  ({size_mb:.1f} MB, {total:.1f}s)")
    print("时间轴核对：")
    for s in tl:
        print(f"  [{s['video_start']:6.1f}s - {s['video_start']+s['dur']:6.1f}s] {s['name']}")


if __name__ == "__main__":
    main()
