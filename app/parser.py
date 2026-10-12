"""PubMed EFetch XML 解析。

实测踩坑（详见 NOTES.md「AI 协作实录」）：
1. ArticleTitle 常含内嵌标签（斜体物种名、下标），必须 itertext() 拼接，.text 会静默丢失后续内容；
2. AbstractText 为结构化分段，Label 属性携带 BACKGROUND/METHODS 等小标题；
3. PubDate 至少有三种形态：Year+Month / MedlineDate("2023 Jan-Feb") / 仅 epub ArticleDate；
4. 作者字段存在 CollectiveName（课题组/联盟署名），不能假定都有 LastName；
5. 约 15% 记录没有 Abstract（letter、comment 等），必须判空。
"""
import re
import xml.etree.ElementTree as ET


def _text(el):
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def _year_from(journal_el, article_el):
    """按 JournalIssue/PubDate → epub ArticleDate 的顺序取发表年份。"""
    if journal_el is not None:
        pubdate = journal_el.find("JournalIssue/PubDate")
        if pubdate is not None:
            y = _text(pubdate.find("Year"))
            if y.isdigit():
                return y
            m = re.match(r"(\d{4})", _text(pubdate.find("MedlineDate")))
            if m:
                return m.group(1)
    ad = article_el.find("ArticleDate")
    if ad is not None:
        y = _text(ad.find("Year"))
        if y.isdigit():
            return y
    return ""


def parse_pubmed_xml(xml_text):
    """把 EFetch 返回的 PubmedArticleSet XML 解析为 dict 列表。"""
    root = ET.fromstring(xml_text)
    articles = []
    for art in root.iter("PubmedArticle"):
        medline = art.find("MedlineCitation")
        if medline is None:
            continue
        article = medline.find("Article")
        if article is None:
            continue

        # 摘要：结构化分段，带 Label
        abstract_parts = []
        abs_el = article.find("Abstract")
        if abs_el is not None:
            for at in abs_el.findall("AbstractText"):
                label = (at.get("Label") or "").strip()
                txt = _text(at)
                if not txt:
                    continue
                abstract_parts.append(f"{label}: {txt}" if label else txt)

        # 期刊信息
        journal_el = article.find("Journal")
        journal_title = _text(journal_el.find("Title")) if journal_el is not None else ""
        journal_abbrev = _text(journal_el.find("ISOAbbreviation")) if journal_el is not None else ""
        issn = _text(journal_el.find("ISSN")) if journal_el is not None else ""

        # MeSH 主题词
        mesh = []
        mesh_list = medline.find("MeshHeadingList")
        if mesh_list is not None:
            for mh in mesh_list.findall("MeshHeading"):
                d = _text(mh.find("DescriptorName"))
                if d:
                    mesh.append(d)

        # 作者（含 CollectiveName）
        authors = []
        author_list = article.find("AuthorList")
        if author_list is not None:
            for au in author_list.findall("Author"):
                coll = _text(au.find("CollectiveName"))
                if coll:
                    authors.append(coll)
                    continue
                name = f'{_text(au.find("LastName"))} {_text(au.find("ForeName"))}'.strip()
                if name:
                    authors.append(name)

        # DOI
        doi = ""
        for aid in art.findall("PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = _text(aid)
                break

        articles.append({
            "pmid": _text(medline.find("PMID")),
            "title": _text(article.find("ArticleTitle")),
            "abstract": "\n".join(abstract_parts),
            "journal": journal_title,
            "journal_abbrev": journal_abbrev,
            "issn": issn,
            "year": _year_from(journal_el, article),
            "mesh": mesh,
            "pub_types": [_text(pt) for pt in article.findall("PublicationTypeList/PublicationType")],
            "authors": authors,
            "doi": doi,
        })
    return articles
