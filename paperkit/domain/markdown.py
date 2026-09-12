"""Markdown 渲染:表格、代码块、行间公式与标题级别。

LaTeXML 的输出结构和普通 HTML 差别很大,这里的取舍全部围绕它:
  * <table> 有三种语义(真表格 / prompt 模板 / 行间公式容器),必须分开处理
  * h1–h6 只是排版标签,真实层级藏在 class 里(见 TITLE_LEVEL)
"""

import re


def render_table(rows: list[list[str]]) -> str:
    """把二维单元格渲染成 Markdown 表格(GFM 管道表)。

    Markdown 只支持单行表头,这里统一把首行当表头:LaTeXML 的 <thead>/<th>
    通常就在首行,即便原表没写 <th>,把首行提升为表头也比留一行空表头更好读。
    多行表头的情况会退化为"首行做表头、其余行当数据",数据不丢。

    竖线在这里才转义(收集期保持原样),因为同一份单元格还可能走
    render_code_block 输出成代码块,那里不需要转义。

    已知取舍:colspan/rowspan 不做展开,跨列单元格只落在第一列、其余列留空,
    因此这类表的列对齐可能与原表不一致(但文字内容不丢)。
    """
    if not rows:
        return ""
    esc = lambda c: c.replace("|", "\\|")  # noqa: E731
    width = max(len(r) for r in rows)
    norm = [list(r) + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(esc(c) for c in norm[0]) + " |",
           "| " + " | ".join(["---"] * width) + " |"]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in norm[1:]]
    return "\n".join(out)


def render_code_block(rows: list[list[str]]) -> str:
    """单列表格渲染成围栏代码块。

    论文里的单列 <table> 基本都是 prompt 模板、对话记录或代码清单,
    套上表头分隔行反而难读,原样放进代码块更贴近原文语义。
    围栏长度取内容中最长连续反引号 +1(至少 3),避免内容里的反引号
    提前把代码块闭合。
    """
    body = "\n".join(r[0] for r in rows if r and r[0])
    if not body:
        return ""
    longest = max((len(m) for m in re.findall(r"`+", body)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{body}\n{fence}"


# 公式编号单元格,形如 "(1)"、"(12a)";排版上属于附属信息,取公式本体时丢掉。
_EQNO_RE = re.compile(r"^\(\d+[a-z]?\)$")


def render_equation_rows(rows: list[list[str]]) -> list[str]:
    """从 LaTeXML 的公式表格里取回公式本体,每个公式一项。

    LaTeXML 把行间公式也包成 <table class="ltx_eqn_table">,格子通常是
    [空白占位, 公式, 编号]。这里滤掉空占位与编号,只留公式;equationgroup
    有多行,就一行一个公式返回。

    与改动前一致:公式编号(1)(2)不保留,因此正文里的"式(1)"无法回指。
    """
    out = []
    for row in rows:
        cells = [c for c in row if c and not _EQNO_RE.match(c.strip())]
        if cells:
            out.append(" ".join(cells))
    return out


# LaTeXML 用同一套 h1–h6 标签承载所有层级的标题,靠 class 区分。直接按标签号
# 映射会把 Abstract(h6) 变成六级标题,所以优先认 class,认不出才退回标签号。
# ltx_title_document 是论文标题本身(正文里会再出现一次),直接丢掉。
TITLE_LEVEL = {
    "ltx_title_abstract": 2,          # h6,但语义上就是一级章节
    "ltx_title_classification": 2,    # h6,keywords
    "ltx_title_section": 2,           # h2  1 Introduction
    "ltx_title_appendix": 2,          # h2  Appendix
    "ltx_title_bibliography": 2,      # h2  References
    "ltx_title_subsection": 3,        # h3  2.1 ...
    "ltx_title_subsubsection": 4,     # h4  3.2.1 ...
    "ltx_title_paragraph": 5,         # h5  无编号的段落式小标题
}
SKIP_TITLE_CLASS = "ltx_title_document"


def heading_level(tag: str, attrs: dict) -> int | None:
    """算出标题该用几级 Markdown;返回 None 表示这不是正文标题。

    级别从 2 起(# 留给论文标题),上限 6。实测 2501.12948 有 86 个标题、
    分属 5 个真实层级,压成清一色 `##` 后就完全看不出 3.2.1 属于 3.2 了。
    """
    classes = (attrs.get("class") or "").split()
    if SKIP_TITLE_CLASS in classes:
        return None
    for cls in classes:
        if cls in TITLE_LEVEL:
            return TITLE_LEVEL[cls]
    try:                      # 认不出 class 就退回标签号
        level = int(tag[1])
    except (IndexError, ValueError):
        return 2
    return min(6, max(2, level))
