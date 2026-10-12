"""LLM 配置一键体检：读取 config.local.py 的 key，逐个尝试候选 base_url，找到可用端点并实测一次对话。

用法：python scripts/check_llm.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app import config

# 候选 base_url：覆盖百炼各地域 + 千问AI平台 + Coding Plan
CANDIDATES = [
    "https://maas.qianwenaiapi.com/compatible-mode/v1",        # 千问AI平台（sk-ws- 新格式 key 的默认签发方）
    "https://dashscope.aliyuncs.com/compatible-mode/v1",       # 百炼 北京
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",  # 百炼 新加坡/国际
    "https://coding.dashscope.aliyuncs.com/compatible-mode/v1",# 百炼 Coding Plan
    "https://dashscope-hk.aliyuncs.com/compatible-mode/v1",    # 中国香港（待验证）
    "https://dashscope-tokyo.aliyuncs.com/compatible-mode/v1", # 东京（待验证）
    "https://dashscope-frankfurt.aliyuncs.com/compatible-mode/v1",  # 法兰克福（待验证）
    "https://dashscope-us.aliyuncs.com/compatible-mode/v1",    # 弗吉尼亚（待验证）
]


async def try_endpoint(client: httpx.AsyncClient, base: str, key: str, model: str):
    """返回 (状态, 模型列表或错误, 聊天结果或错误)"""
    headers = {"Authorization": f"Bearer {key}"}
    # 1) 模型清单
    try:
        r = await client.get(f"{base}/models", headers=headers)
    except Exception as e:
        return "unreachable", f"{type(e).__name__}", None
    if r.status_code != 200:
        try:
            msg = r.json().get("error", {}).get("message", r.text[:120])
        except Exception:
            msg = r.text[:120]
        return f"HTTP {r.status_code}", msg, None
    try:
        data = r.json()
        models = [m.get("id") for m in data.get("data", [])]
    except Exception:
        models = []
    # 2) 实测对话
    chat = None
    try:
        r2 = await client.post(
            f"{base}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": "用一句话介绍你自己"}],
                "max_tokens": 60,
            },
        )
        if r2.status_code == 200:
            chat = r2.json()["choices"][0]["message"]["content"][:80]
        else:
            chat = f"HTTP {r2.status_code}: {r2.text[:150]}"
    except Exception as e:
        chat = f"{type(e).__name__}: {e}"
    return "OK", models, chat


async def main():
    key = config.get("LLM_API_KEY")
    model = config.get("LLM_MODEL")
    print(f"key: {key[:10]}...{key[-6:]}  (len={len(key)})")
    print(f"model: {model}\n")
    async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
        found = False
        for base in CANDIDATES:
            status, detail, chat = await try_endpoint(client, base, key, model)
            print(f"[{status}] {base}")
            if status == "OK":
                found = True
                qwen = [m for m in detail if m and "qwen" in m.lower()]
                print(f"  models({len(detail)}): {', '.join(qwen[:12])}{' ...' if len(qwen) > 12 else ''}")
                print(f"  chat[{model}]: {chat}")
                print(f"\n==> 可用端点：{base}")
                if model not in (detail or []):
                    print(f"!!! 注意：模型 '{model}' 不在可用列表里，请从上面挑一个替换 LLM_MODEL")
            else:
                print(f"  {detail}")
        if not found:
            print("\n==> 所有候选端点均拒绝该 key。请确认：")
            print("  1. key 是在哪个平台申请的（百炼控制台 / 千问AI平台 / 第三方中转站）？")
            print("  2. 中转站 key 必须配中转站自己的 base_url，官方域名用不了")
            print("  3. key 是否配置了 IP 白名单（本机出口 IP 需在名单内）")


if __name__ == "__main__":
    asyncio.run(main())
