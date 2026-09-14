"""LaTeXML 渲染的论文 HTML → 区块序列。

纯函数:只依赖字符串输入,不碰网络与磁盘,因此可以完全离线测试。
"""

import re
from html.parser import HTMLParser

from .markdown import heading_level, render_code_block, render_equation_rows, render_table

MIN_PARA_CHARS = 40  # 短于此的段落视为导航/噪声,丢弃


def _graphic_src(tag: str, attrs: dict) -> str:
    """从 <img>/<object> 的属性里取图片地址,取不到返回空串。

    LaTeXML 渲染的论文里,大多数插图不是 <img> 而是
    <object type="image/svg+xml" data="...">,只认 <img src> 会漏掉绝大多数图。

    <object> 也可能用来嵌入非图片内容,所以 type 存在时必须是以 image/ 开头;
    <img> 则额外兼容几种懒加载写法与 srcset。
    """
    if tag == "object":
        typ = (attrs.get("type") or "").strip().lower()
        if typ and not typ.startswith("image/"):
            return ""
    src = (attrs.get("src") or attrs.get("data") or attrs.get("data-src") or
           attrs.get("data-lazy-src") or attrs.get("data-original"))
    if not src and attrs.get("srcset"):
        src = attrs["srcset"].split(",")[0].strip().split(" ")[0]
    return (src or "").strip()


class PaperHTMLParser(HTMLParser):
    """从 arXiv/ar5iv 的 HTML 中抽取标题、正文段落与表格。

    这是事件驱动的流式解析:HTMLParser 边扫标签边回调,我们不建 DOM 树。
    状态用四个实例变量维护:
      _blocks  结果列表,kind 为 "p"/"table"/"verbatim"/"formula"/"image",
               标题则为 "h2"–"h6"(级别由 heading_level() 判定)
      _skip    正在跳过的标签栈(遇到 </x> 弹出),用于忽略 script/svg 等
      _buf     当前正在累积的文本;进入 <p>/<h*>/<figcaption>/<td> 时置空
               开始收集,遇到结束标签时 _flush() 收尾——这样标签内再嵌
               <span>、<b> 等行内标签也不受影响,文本自然接在一起。
      _table   正在收集的表格 {"rows": [[单元格,...]], "row": [...]}
               _table_depth 记录嵌套层数,只在最外层(depth==1)建结构,
               嵌套表的内容直接并入外层单元格文本,避免结构错乱。

    四类特殊处理:
      - <math> 用其 alttext 以 $...$ 形式内联,避免公式变成乱码
      - 跳过 script/style/svg 与参考文献(ltx_bibliograph)
      - 图注(figcaption)加【图注】前缀保留为独立段落
      - 表格分三种走法:真表格渲染成 Markdown 表(render_table);单列表格
        其实是 prompt 模板/清单,转代码块(render_code_block);
        <table class="ltx_eqn_table"> 实为行间公式容器,按 formula 输出
      - 单元格内的 <p>/<h*> 不当新块处理,否则一个格子会被拆成多格
    """

    # 段落级容器:进入时开新缓冲,结束时结算
    _BLOCK_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "figcaption")

    def __init__(self):
        # convert_charrefs=True: &amp; 这类 HTML 实体自动解码成普通字符
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []
        self._skip: list[str] = []
        self._buf: str | None = None
        self._kind = "p"
        self._table: dict | None = None
        self._table_depth = 0
        # 解析过程中见到过几张图(<img> 与 <object type="image/*"> 都算)。
        # parse_blocks 用它判断是否需要走正则兜底,比"结果里有没有 image 块"
        # 更准——表格内的图片是内联进单元格的,按结果判断会误触发兜底。
        self.graphic_count = 0

    def _skip_this(self, tag: str, attrs: dict) -> bool:
        """判断某标签子树是否整体不要(脚本/样式/参考文献)。"""
        if tag in ("script", "style", "svg", "noscript"):
            return True
        # 参考文献整体跳过:正文里的 [12] 目前回溯不到条目,留着反而误导
        return "ltx_bibliograph" in attrs.get("class", "")

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)

        # 跳过判定放在最前面:script/svg/参考文献里的 <img> 也不该被收进来。
        if self._skip:  # 已在跳过中:嵌套的可跳过标签入栈,其余无视
            if self._skip_this(tag, a) or tag == "math":
                self._skip.append(tag)
            return
        if self._skip_this(tag, a):
            self._skip.append(tag)
            return

        if tag in ("img", "object"):
            src = _graphic_src(tag, a)
            if not src:
                return
            self.graphic_count += 1
            alt = a.get("alt", "").strip()
            if self._buf is not None:   # 单元格/段落内的图片:内联进去
                self._buf += f" ![{alt}]({src}) "
            else:
                self.blocks.append(("image", f"{src}\t{alt}"))
            if tag == "object":
                # <object> 可能带回退内容,整棵子树跳过,免得同一张图收两遍
                self._skip.append("object")
            return

        if tag == "math":  # 公式以内联 LaTeX 呈现
            alt = (a.get("alttext") or "").replace("\n", " ")
            in_eq_table = self._table is not None and self._table["equation"]
            if alt and self._buf is not None:
                # 公式表格里的 math 本身就是行间公式,输出时外层会补 $$,
                # 这里不能再包 $...$,否则会渲染成 $$ $...$ $$。
                self._buf += f" {alt} " if in_eq_table else f" ${alt}$ "
            elif alt:
                self.blocks.append(("formula", alt.strip()))
            self._skip.append(tag)  # <math> 的渲染内容不要,只要 alttext
            return

        # ---- 表格:表格结构靠 td/th/tr 事件拼,文本仍走 _buf ----
        if tag == "table":
            if self._buf is not None:  # 表格前的残段先结算
                self._flush()
            self._table_depth += 1
            if self._table_depth == 1:  # 只有最外层建结构
                # LaTeXML 把行间公式也包在 <table class="ltx_eqn_table"> 里,
                # 它没有表格语义,得按公式输出,否则公式会变成一行怪表。
                self._table = {"rows": [], "row": [],
                               "equation": "ltx_eqn_table" in a.get("class", "")}
            return
        if self._table_depth == 1:
            if tag == "tr":
                self._end_cell()
                self._end_row()
                return
            if tag in ("td", "th"):
                self._end_cell()
                self._buf = ""
                self._kind = "cell"
                return

        if tag == "br" and self._buf is not None:
            self._buf += "<br>"   # 单元格内换行:Markdown 表格里靠 <br> 保位
            return

        if tag in self._BLOCK_TAGS:
            if self._kind == "cell":
                # 格子里的 <p>/<h*> 不另起块,否则一格会被拆成多格;
                # 但补一个空格,免得两段文字直接粘连。
                if self._buf is not None:
                    self._buf += " "
                return
            if self._buf is not None:  # 上一段没闭合就开了新段:先结算
                self._flush()
            if tag.startswith("h"):
                level = heading_level(tag, a)
                if level is None:
                    return             # 论文标题本身,正文里跳过
                self._kind = f"h{level}"
            else:
                self._kind = "p"
            self._buf = ""
            if tag == "figcaption":
                self._kind = "cap"

    def handle_endtag(self, tag):
        if self._skip:  # 只有栈顶标签的 </x> 才弹栈,防止嵌套误配
            if tag == self._skip[-1]:
                self._skip.pop()
            return
        if tag == "table":
            if self._table_depth == 1:
                self._end_cell()
                self._end_row()
                self._flush_table()
            self._table_depth = max(0, self._table_depth - 1)
            return
        if self._table_depth == 1:
            if tag in ("td", "th"):
                self._end_cell()
                return
            if tag == "tr":
                self._end_cell()
                self._end_row()
                return
        if tag in self._BLOCK_TAGS:
            if self._kind == "cell":
                return
            if self._buf is not None:
                self._flush()

    def handle_data(self, data):
        """纯文本节点:不在跳过区且正在收集段落时,追加进缓冲。"""
        if self._skip or self._buf is None:
            return
        self._buf += data

    # ---- 表格收集的三个收尾动作 ----
    def _end_cell(self):
        """结束当前单元格:把缓冲结算进当前行。"""
        if self._kind == "cell":
            if self._buf is not None:
                self._flush()
            self._kind = "p"

    def _end_row(self):
        """结束当前行:非空行才入表,避免 <tr> 里的空白产生幽灵行。"""
        if self._table is not None and any(self._table["row"]):
            self._table["rows"].append(self._table["row"])
        if self._table is not None:
            self._table["row"] = []

    def _flush_table(self):
        """表格结束:公式表拆成 formula 块,单列表格转代码块,其余转 Markdown。"""
        table, self._table = self._table, None
        if not table or not table["rows"]:
            return
        if table["equation"]:
            for eq in render_equation_rows(table["rows"]):
                self.blocks.append(("formula", eq))
            return
        if max(len(r) for r in table["rows"]) == 1:
            code = render_code_block(table["rows"])
            if code:
                self.blocks.append(("verbatim", code))
            return
        md = render_table(table["rows"])
        if md:
            self.blocks.append(("table", md))

    def _flush(self):
        """结束一个区块:压缩空白、按类型过滤噪声后存入结果。"""
        text = re.sub(r"\s+", " ", self._buf or "").strip()
        kind, self._buf = self._kind, None
        if kind == "cell":
            # 单元格不做长度过滤("1.2" 这种短值也要留);竖线转义推迟到
            # 渲染期,因为单列表格会走代码块输出、那时不需要转义。
            if self._table is not None:
                self._table["row"].append(text)
        elif kind.startswith("h"):
            if text:
                self.blocks.append((kind, text))
        elif kind == "cap":
            if len(text) >= 20:  # 太短的图注多为 "(a)" 之类的编号
                self.blocks.append(("p", "【图注】" + text))
        else:
            if len(text) >= MIN_PARA_CHARS:
                self.blocks.append(("p", text))


def parse_blocks(html: str) -> list[tuple[str, str]]:
    """HTML → 区块序列(kind 为 h/p/table/verbatim/formula/image)。

    先做字符串级裁剪:只保留 <div class="ltx_page_main">(论文正文容器)
    到页脚之间的部分,把 ar5iv/arxiv 页面的导航按钮、页脚等噪声整个
    切掉——这比在解析器里逐个过滤省事得多。
    """
    start = html.find("ltx_page_main")
    if start != -1:
        html = html[start:]
    for stop in ("ltx_page_footer", "</article>", "</body>"):
        end = html.find(stop)
        if end != -1:
            html = html[:end]
            break
    p = PaperHTMLParser()
    p.feed(html)
    # Some arXiv HTML variants use malformed/lazy-loaded image markup that
    # HTMLParser may skip. Recover image sources from the same main-content HTML.
    # 用解析期见到的图片计数判断,而不是看结果里有没有 image 块——表格内的
    # 图片现在是内联进单元格的,按结果判断会误触发兜底、把图重复加一遍。
    if p.graphic_count == 0:
        # 兜底扫描是字符串级的,不认 skip 栈,所以只扫到参考文献为止,
        # 免得把里面的图也捞出来(参考文献恒在正文之后,截断即可)。
        bib = html.find("ltx_bibliograph")
        scan = html[:bib] if bib != -1 else html
        for match in re.finditer(r"<(img|object)\b([^>]*)>", scan, re.I | re.S):
            attrs = dict(re.findall(r'''([\w:-]+)\s*=\s*["']([^"']*)["']''',
                                    match.group(2)))
            src = _graphic_src(match.group(1).lower(), attrs)
            if src:
                p.blocks.append(("image", f"{src}\t{attrs.get('alt', '').strip()}"))
    return p.blocks
