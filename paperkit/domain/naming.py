"""文件名与目录名生成。

目标平台是 Windows,因此要避开 <>:"/\\|?* 这些字符,并注意长度上限。
"""

import re
import unicodedata


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
