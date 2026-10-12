# 复制本文件为 config.local.py 并填入密钥（config.local.py 已被 .gitignore，不会进仓库）

# PubMed E-utilities API Key
# 申请地址：https://www.ncbi.nlm.nih.gov/account/settings/ → API Key Management
# 留空则按 3 次/秒限速运行（功能不受影响，仅稍慢）
PUBMED_API_KEY = ""

# LLM（OpenAI 兼容协议）。默认阿里云百炼 DashScope 兼容模式
# 留空时统计/图表/Top100 照常工作，综述走统计模板兜底
LLM_API_KEY = ""
LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL = "qwen3.7-flash"

# 服务监听（一般不用改）
# HOST = "127.0.0.1"
# PORT = 8000
