# 复制本文件为 config.local.py 并填入密钥（config.local.py 已被 .gitignore，不会进仓库）

# PubMed E-utilities API Key
# 申请地址：https://www.ncbi.nlm.nih.gov/account/settings/ → API Key Management
# 现行格式为 36 位小写十六进制，以账号页实际显示为准，原样复制（不要手动转录）
# 留空则按 3 次/秒限速运行（功能不受影响，仅稍慢）
PUBMED_API_KEY = ""

# LLM（OpenAI 兼容协议），默认通义千问
# sk-ws- 新格式 key（千问AI平台签发）：用 https://maas.qianwenaiapi.com/compatible-mode/v1
# 旧格式/百炼北京 key：用 https://dashscope.aliyuncs.com/compatible-mode/v1
# 第三方中转站 key：必须配中转站自己的 base_url，官方域名用不了
# 留空时统计/图表/Top100 照常工作，综述走统计模板兜底
# 验证 key 请用 scripts/check_llm.py（从本文件读取），不要把 key 写进命令行
LLM_API_KEY = ""
LLM_BASE_URL = "https://maas.qianwenaiapi.com/compatible-mode/v1"
LLM_MODEL = "qwen3.7-flash"

# 服务监听（一般不用改）
# HOST = "127.0.0.1"
# PORT = 8000
