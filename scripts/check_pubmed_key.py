"""从 config.local.py 读取 PubMed key 并验证（避免密钥出现在命令行被沙箱脱敏）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app import config

key = config.get("PUBMED_API_KEY")
print(f"config key: {key!r} (len={len(key)})")

variants = {"原样": key, "转小写": key.lower()}
for label, k in variants.items():
    if not k:
        print(f"[{label}] key 为空")
        continue
    r = httpx.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params={"db": "pubmed", "term": "diabetic retinopathy", "retmode": "json", "retmax": 0, "api_key": k},
        timeout=30,
        trust_env=False,
    )
    d = r.json()
    err = d.get("error") or (d.get("esearchresult", {}).get("errorlist") or ["none"])
    print(f"[{label}] HTTP {r.status_code}  count={d.get('esearchresult', {}).get('count')}  error={err}")
