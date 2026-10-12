"""磁盘缓存：同一关键词 + 参数的完整结果直接命中，保证现场演示秒出。"""
import hashlib
import json
import os
import time

from . import config

CACHE_DIR = os.path.join(config.BASE_DIR, "cache")
TTL_SECONDS = 7 * 24 * 3600


def _path(key):
    return os.path.join(CACHE_DIR, f"{key}.json")


def make_key(*parts):
    raw = "|".join(str(p) for p in parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def get(key):
    path = _path(key)
    if not os.path.exists(path):
        return None
    try:
        if time.time() - os.path.getmtime(path) > TTL_SECONDS:
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def set(key, data):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_path(key), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass  # 缓存失败不阻塞主流程
