"""分析引擎：期刊指标 join、统计、词云词频、近N年 IF TopN。"""
import re
import statistics
from collections import Counter
from datetime import datetime

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "were", "was", "are",
    "have", "has", "had", "not", "but", "its", "our", "their", "his", "her",
    "after", "before", "between", "during", "using", "based", "study", "studies",
    "analysis", "review", "report", "case", "cases", "patients", "patient",
    "results", "result", "methods", "method", "objective", "background",
    "conclusion", "conclusions", "data", "group", "groups", "effect", "effects",
    "associated", "association", "compared", "versus", "among", "into", "than",
    "more", "most", "less", "over", "under", "within", "without", "also",
    "such", "each", "both", "when", "where", "which", "while", "been", "being",
}


def current_year():
    return datetime.now().year


def enrich_with_journal(articles, jdb):
    """把期刊指标 join 到文献上，返回新列表。"""
    out = []
    for a in articles:
        j = jdb.lookup(a.get("issn", ""), a.get("journal", ""), a.get("journal_abbrev", ""))
        b = dict(a)
        if j:
            b["if"] = j.get("if")
            b["zone"] = str(j.get("cas", ""))
            b["jcr_q"] = j.get("q", "")
            b["journal_matched"] = j.get("name", "")
        else:
            b["if"] = None
            b["zone"] = None
            b["jcr_q"] = None
            b["journal_matched"] = None
        out.append(b)
    return out


def _title_tokens(title):
    words = re.findall(r"[a-z][a-z-]{3,}", (title or "").lower())
    return [w for w in words if w not in STOPWORDS and not w.isdigit()]


def build_wordcloud(articles, top_n=120):
    """MeSH 主题词为主（权重 2），标题实词为辅（权重 1）。"""
    counter = Counter()
    for a in articles:
        for m in a.get("mesh", []):
            counter[m] += 2
        for t in _title_tokens(a.get("title", "")):
            counter[t] += 1
    return [{"name": n, "value": v} for n, v in counter.most_common(top_n)]


def build_stats(enriched, total_count, recent_count, top_n=100, review_years=5):
    cy = current_year()
    recent_ratio = round(recent_count / total_count, 4) if total_count else None

    year_dist = Counter(a["year"] for a in enriched if a.get("year"))
    journal_dist = Counter(a.get("journal") or a.get("journal_abbrev") or "未知期刊" for a in enriched)
    zone_dist = Counter(a.get("zone") or "none" for a in enriched)

    ifs = [a["if"] for a in enriched if a.get("if") is not None]
    median_if = round(statistics.median(ifs), 1) if ifs else None
    matched = sum(1 for a in enriched if a.get("journal_matched"))
    matched_ratio = round(matched / len(enriched), 4) if enriched else 0

    # 影响力榜单：仅对有 IF 的文献按 (IF, 年份) 降序
    ranked = sorted(
        [a for a in enriched if a.get("if") is not None],
        key=lambda a: (a["if"], int(a["year"]) if a.get("year", "").isdigit() else 0),
        reverse=True,
    )[:top_n]
    top_list = []
    for i, a in enumerate(ranked, 1):
        top_list.append({
            "rank": i,
            "pmid": a.get("pmid", ""),
            "title": a.get("title", ""),
            "journal": a.get("journal_matched") or a.get("journal") or a.get("journal_abbrev") or "",
            "year": a.get("year", ""),
            "if": a.get("if"),
            "zone": a.get("zone") or "",
            "jcr_q": a.get("jcr_q") or "",
            "doi": a.get("doi", ""),
        })

    journal_top = []
    for name, cnt in journal_dist.most_common(10):
        sample = next((a for a in enriched if (a.get("journal") or a.get("journal_abbrev")) == name), None)
        journal_top.append({"journal": name, "count": cnt, "if": (sample or {}).get("if")})

    return {
        "total_count": total_count,
        "recent_count": recent_count,
        "analyzed_count": len(enriched),
        "recent_ratio": recent_ratio,
        "median_if": median_if,
        "q1_ratio": round(zone_dist.get("1", 0) / len(enriched), 4) if enriched else 0,
        "matched_ratio": matched_ratio,
        "zone_dist": {k: zone_dist.get(k, 0) for k in ("1", "2", "3", "4", "none")},
        "year_dist": dict(sorted(year_dist.items())),
        "journal_top": journal_top,
        "top_n": top_list,
    }
