"""纯论文领域规则:arXiv id 解析、文件名生成。

本模块**只允许**纯函数——不读写文件、不发网络请求、不读全局配置。
这条约束由 tests/test_layering.py 在 CI 层强制。
"""

import re
import unicodedata

# arXiv 的两代 id 格式:新版 0704.0001 式,旧版 cs/0703045 式
# (archive 小写,可带 - 与 .子类,如 hep-th、cond-mat、math.GT、astro-ph)
NEW_ID = r"[0-9]{4}\.[0-9]{4,5}"
OLD_ID = r"[a-z][a-z\-]*(?:\.[A-Za-z]{2})?/[0-9]{7}"


def parse_arxiv_id(text: str) -> str | None:
    """从各种输入形态提取 arXiv id(如 '2501.12948'),认不出返回 None。

    兼容:新版裸 id '2501.12948v2'、旧版 id 'cs/0703045' / 'hep-th/9901001' /
    'math.GT/0309136',以及 abs / pdf 链接。返回时统一去掉版本后缀 vN。
    两个正则的区别:search 允许嵌在 URL 里,fullmatch 要求整串完全匹配。
    """
    text = text.strip()
    idpat = f"(?:{NEW_ID}|{OLD_ID})"
    m = re.search(rf"arxiv\.org/(?:abs|pdf)/({idpat})(v\d+)?", text, re.I)
    if m:
        return m.group(1)
    m = re.fullmatch(rf"({idpat})(v\d+)?", text)
    if m:
        return m.group(1)
    return None


def sanitize(name: str) -> str:
    """把任意字符串变成合法的 Windows 文件/目录名。

    三步:NFKC 规范化(全角→半角等)→ 删非法字符 → 压空白、去首尾点。
    """
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:200]


def make_filename(meta: dict) -> str:
    """生成 '年份 - 第一作者 et al. - 标题 [id].pdf'。

    先 sanitize 再截断到 180 字符、最后拼 .pdf——顺序不能反,
    否则超长标题会把 .pdf 后缀截掉(早期版本的 bug)。
    """
    authors = meta.get("authors") or []
    if authors:
        first = authors[0].split()[-1]           # 取第一作者的姓(最后一个词)
        etal = " et al." if len(authors) > 1 else ""
    else:
        first, etal = "Unknown", ""
    base = sanitize(f"{meta['year']} - {first}{etal} - {meta['title']} [{meta['id']}]")
    return base[:180] + ".pdf"
