"""期刊静态指标库：影响因子 + 中科院大类分区 + JCR 分区。

重要口径声明（README / 页面同步展示）：
PubMed E-utilities 不提供影响因子与分区数据。本库为离线整理的静态示例库
（data/journals.json，版本见 meta.version），用于演示完整数据流；
生产环境应替换为权威数据源（中科院分区官方 / LetPub / 期刊官网），
接口已隔离在 JournalDB.lookup()，换数据源不改业务代码。
"""
import json
import os
import re

from . import config


def _norm(s):
    s = (s or "").lower()
    s = re.sub(r"[.\s]+", " ", s).strip()
    if s.startswith("the "):
        s = s[4:]
    return s


class JournalDB:
    def __init__(self, path=None):
        path = path or os.path.join(config.BASE_DIR, "data", "journals.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.version = data.get("meta", {}).get("version", "unknown")
        self.note = data.get("meta", {}).get("note", "")
        self._by_issn = {}
        self._by_name = {}
        for j in data.get("journals", []):
            issn = (j.get("issn") or "").strip()
            if issn:
                self._by_issn[issn.replace("-", "")] = j
            for key in (_norm(j.get("name")), _norm(j.get("abbrev"))):
                if key:
                    self._by_name.setdefault(key, j)

    def lookup(self, issn="", journal_title="", abbrev=""):
        """ISSN 优先（去连字符精确匹配）→ 刊名归一化 → 缩写归一化；未命中返回 None。"""
        issn_key = (issn or "").replace("-", "").strip()
        if issn_key and issn_key in self._by_issn:
            return self._by_issn[issn_key]
        for key in (_norm(journal_title), _norm(abbrev)):
            if key and key in self._by_name:
                return self._by_name[key]
        return None
