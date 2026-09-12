"""arXiv id 解析。

支持两代 id:新版 0704.0001 式,旧版 cs/0703045 式(2022 年以前的老论文
全用后者)。也接受嵌在 abs / pdf 链接里的形式。
"""

import re


# arXiv 的两代 id 格式(archive 小写,可带 - 与 .子类,如 hep-th、math.GT)
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
