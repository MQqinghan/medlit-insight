"""配置加载：优先读项目根目录 config.local.py（已被 gitignore），其次环境变量，最后默认值。

密钥不进 git：复制 config.local.example.py 为 config.local.py 后填写即可。
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    # ---- PubMed E-utilities ----
    "PUBMED_API_KEY": "",            # NCBI API Key（账号 Settings 页申请），留空则按 3 req/s 限速
    "PUBMED_TOOL": "medlit-insight", # NCBI 要求标识工具名
    "PUBMED_EMAIL": "demo@example.com",
    # ---- LLM（OpenAI 兼容协议；默认阿里云百炼 DashScope 兼容模式）----
    "LLM_API_KEY": "",
    "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "LLM_MODEL": "qwen3.7-flash",
    # ---- 服务 ----
    "HOST": "127.0.0.1",
    "PORT": 8000,
    # ---- 分析参数 ----
    "MAX_FETCH": 2000,               # 单次分析最多抓取的近5年文献数（样本上限）
    "FETCH_BATCH": 200,              # efetch 每批 UID 数
    "TOP_N": 100,                    # 影响力榜单条数
    "REVIEW_YEARS": 5,               # 近N年窗口
    "TREND_YEARS": 10,               # 年度趋势图回溯年数（按年精确计数）
}


def _load_local_overrides():
    path = os.path.join(BASE_DIR, "config.local.py")
    overrides = {}
    if os.path.exists(path):
        namespace = {}
        with open(path, "r", encoding="utf-8") as f:
            exec(compile(f.read(), path, "exec"), namespace)
        overrides = {k: v for k, v in namespace.items() if k.isupper() and not k.startswith("_")}
    return overrides


_OVERRIDES = _load_local_overrides()


def get(key):
    if key in _OVERRIDES:
        return _OVERRIDES[key]
    return os.environ.get(key, DEFAULTS.get(key, ""))
