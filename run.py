"""PyCharm 一键启动：直接 Run 本文件即可（无需命令行、无需环境变量）。

密钥配置：复制项目根目录 config.local.example.py 为 config.local.py 填入。
没有密钥时，统计 / 图表 / Top100 照常工作，仅 LLM 综述走模板兜底。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _bootstrap():
    # 只追加 NO_PROXY（回环地址绕过代理），不删 HTTP_PROXY——服务出网调 NCBI 可能依赖代理
    ex = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    local = "127.0.0.1,localhost,0.0.0.0,::1"
    os.environ["NO_PROXY"] = f"{ex},{local}" if ex else local
    os.environ["no_proxy"] = os.environ["NO_PROXY"]
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


_bootstrap()

import uvicorn  # noqa: E402

from app.config import get  # noqa: E402
from app.main import app  # noqa: E402

if __name__ == "__main__":
    host = get("HOST")
    port = int(get("PORT"))
    print(f"\n  文献罗盘已启动 →  http://{host}:{port}")
    print("  停止：PyCharm 点红色方块 / Ctrl+C\n")
    # 直接传 app 对象，避免字符串导入在不同工作目录下失败
    uvicorn.run(app, host=host, port=port, reload=False)
