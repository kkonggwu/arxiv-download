"""LaTeXML 渲染的论文 HTML → 区块序列。

纯函数:只依赖字符串输入,不碰网络与磁盘,因此可以完全离线测试。
"""

import html
import re
from html.parser import HTMLParser

from .markdown import heading_level, render_code_block, render_equation_rows, render_table
from .naming import sanitize

MIN_PARA_CHARS = 40  # 短于此的段落视为导航/噪声,丢弃

# LaTeXML 给插图的内联 SVG 打的类名。只认这个类,不能见 <svg> 就收:
# 页面上还有导航/主题切换按钮等 role="presentation" 的 <svg>,收进来就是垃圾。
PICTURE_CLASS = "ltx_picture"


def _start_name(raw: str) -> str:
    """从原始起始标签文本里取标签名,**保留大小写**。

    HTMLParser 会把标签名统一转小写后再交给回调,而 SVG 里
    foreignObject / clipPath / linearGradient 这类驼峰标签是大小写敏感的:
    用回调给的 tag 拼结束标签会拼出 </foreignobject>,和 <foreignObject>
    对不上,整份 .svg 就成了非法 XML(实测 10 张内联图全部中招)。
    """
    m = re.match(r"<\s*([^\s/>]+)", raw)
    return m.group(1) if m else ""


# HTML 的空元素:有起始标签但没有结束标签。采集内联插图时**不能**把它们
# 压栈——它们永远等不到配对的结束标签,会一直压在栈顶,把后面真正的配对
# 全部挡掉。实测 2501.12948 的 A2.SS2.p1.pic1 里 9 个 <br class="ltx_break">
# 就是这么让 </foreignObject> 退化成小写、产出非法 XML 的。
VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})


def _self_close(raw: str) -> str:
    """把 `<br class="x">` 补成 `<br class="x"/>`。

    空元素的 HTML 写法在 XML 里是非法的:没有结束标签,后面所有标签都会被
    当成它的子节点,整份 .svg 报 mismatched tag。补成自闭合既过得了 XML
    校验,渲染语义也不变(这些标签只出现在 foreignObject 里,而那块内容
    最终会被扁平化或整块降级)。
    """
    stripped = raw.rstrip()
    if stripped.endswith("/>"):
        return raw
    return stripped[:-1].rstrip() + "/>"


def _close_names(stack: list[str], tag: str) -> list[str]:
    """给结束标签找回原始大小写,并补上压在它上面的未闭合元素。

    返回要依次写出的结束标签名,可能不止一个:HTML 里未闭合的行内标签很
    常见(LaTeXML 的 <span> 就常常不闭合)。只写一个 </clipPath> 会留下
    `<span>x</clipPath>` 这种缺结束标签的非法标记;把隐含闭合的补上才是
    忠实还原。

    只比对栈顶不够稳:栈顶一旦不是要找的标签,配对就会失败并退化成小写
    标签名。所以从栈顶往下找。真的找不到对应起始标签时,原样返回(小写)
    交给下游。
    """
    for i in range(len(stack) - 1, -1, -1):
        if stack[i].lower() == tag:
            names = list(reversed(stack[i:]))     # 隐含闭合的排在前
            del stack[i:]
            return names
    return [tag]


SVG_NS = 'xmlns="http://www.w3.org/2000/svg"'

# 基线在文本框内的位置(单位:em)。不是拍脑袋定的:对着原始内联渲染做像素级
# 扫描,0.45→0.70 步进 0.05,三张图都在 0.60 取到最小差(其中一张 0.70 与
# 0.60 相差 0.1%,视为并列)。换公式前请重跑标定。
BASELINE_RATIO = 0.6

_FOREIGN = re.compile(r"<foreignObject\b([^>]*)>(.*?)</foreignObject>", re.S | re.I)
_MATRIX = re.compile(r"matrix\(([^)]*)\)")
_FONT_SIZE = re.compile(r"font-size:([\d.]+)pt")
_ALT_TEXT = re.compile(r'alttext="([^"]*)"')
_ANY_TAG = re.compile(r"<[^>]+>")
# 内层 span 常常再缩一次字号,实测 2201.11903 上有 90% 与 80% 两种。
# 漏掉它文字会整体偏大,密排的刻度/图例就叠在一起。
_FO_SCALE = re.compile(r"font-size:\s*([\d.]+)%")
_BR = re.compile(r"<br\b[^>]*>", re.I)
_MATH = re.compile(r"<math\b([^>]*)>(.*?)</math>", re.S | re.I)
_ANNOTATION = re.compile(r"<annotation\b.*?</annotation>", re.S | re.I)

# 判为「正文图」所需的纯文本量。实测样本是 1729 字,离阈值有 8 倍余量;
# 图表图例/坐标轴标签通常在几十字以内,不会误触。
MIN_FLOW_CHARS = 200


def _fo_is_flow(inner: str) -> bool:
    """判断 foreignObject 装的是「正文」还是「图形标签」。

    LaTeXML 的图表标签是零散的单行文本(刻度、图例、子图标题);而有些
    「图」其实是排版好的文本块——prompt 模板、清单、算法伪码,外层套
    ltx_minipage,内部用 <br> 或 ltx_p 分段。实测 2501.12948 的
    A2.SS2.p1.pic1 就是这样一张 7 段、1729 字的提示词模板。

    两个条件都要满足,是为了不误伤:只看 <br> 会把「图例里换了一行」的
    图表判成正文,整张图降级成文本、图形全丢;只看结构标记又可能把图里
    一小段说明文字当成正文。要求纯文本量足够大,才说明文字是这张图的
    主体,而不是附属标签。
    """
    low = inner.lower()
    if "ltx_minipage" not in low and low.count("<br") < 3:
        return False
    return len(_fo_flow_text(inner)) >= MIN_FLOW_CHARS


def _fo_flow_text(inner: str) -> str:
    """取正文块的全部文字:<br> 还原成换行,行内公式取其可见字形。"""
    def math_rep(m: re.Match) -> str:
        # 正文里的行内公式,<mo> 里是可直接显示的字符(≫ > =);退而求其次
        # 才用 alttext,那是 LaTeX 源码(\gg),给读者看不如字形直观。
        body = _ANNOTATION.sub("", m.group(2))
        plain = re.sub(r"\s+", "", _ANY_TAG.sub("", body))
        if plain:
            return plain
        alt = _ALT_TEXT.search(m.group(1))
        return alt.group(1) if alt else ""

    text = _MATH.sub(math_rep, inner)
    text = html.unescape(_ANY_TAG.sub("", _BR.sub("\n", text)))
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(lines).strip()


def _fo_plain(inner: str) -> str:
    """取 foreignObject 里的文字。

    两种形态:数字类刻度用 `<math alttext="20">`,说明性标签用
    `<span class="ltx_text">Solve rate (%)</span>`。前者直接取 alttext,
    后者剥标签取纯文本。
    """
    m = _ALT_TEXT.search(inner)
    if m:
        return html.unescape(m.group(1))
    return re.sub(r"\s+", " ", html.unescape(_ANY_TAG.sub("", inner))).strip()


def _fo_scale(inner: str) -> float:
    """内层 span 的额外字号缩放,没有就是 1。"""
    m = _FO_SCALE.search(inner)
    return float(m.group(1)) / 100 if m else 1.0


def _flatten_foreign_objects(markup: str) -> str:
    """把 <foreignObject> 里的 HTML/MathML 文字转成 SVG 原生 <text>。

    为什么必须转:SVG 被 `<img>` 引用时,浏览器进入「安全静态模式」,
    foreignObject 的内容一律不渲染。实测 2201.11903 的 10 张内联图抽成
    独立文件后,坐标轴刻度、图例、标题**全部消失**,只剩光秃秃的曲线——
    图形是对的,但读不懂。

    位置还原:LaTeXML 的 foreignObject 不带 x/y,靠祖先 <g> 的 translate
    定位,自身带一个垂直翻转 `matrix(1 0 0 -1 0 T)`——因为框里的 HTML 是
    y 向下排版的。所以这里**原样保留那个 transform** 搬到 <text> 上,让
    两级翻转相互抵消,文字才是正的(不保留就会整片倒过来)。
    基线落在框内 `T + BASELINE_RATIO × 字号` 处。
    """
    def rep(m: re.Match) -> str:
        attrs, inner = m.group(1), m.group(2)
        text = _fo_plain(inner)
        matrix, size = _MATRIX.search(attrs), _FONT_SIZE.search(attrs)
        if not text or not matrix or not size:
            return ""            # 取不到位置就不放,免得文字飘到错误的地方
        try:
            shift = float(matrix.group(1).split()[-1])
            # round 掉浮点尾差(9.25 × 0.9 会算出 8.325000000000001)
            font = round(float(size.group(1)) * _fo_scale(inner), 3)
        except (ValueError, IndexError):
            return ""
        y = shift + BASELINE_RATIO * font
        return (f'<text x="0" y="{y:.2f}" '
                f'transform="matrix(1 0 0 -1 0 {shift})" '
                f'font-size="{font:g}pt" font-family="serif" '
                f'fill="#000">{html.escape(text)}</text>')

    return _FOREIGN.sub(rep, markup)


def _flow_text(markup: str) -> str:
    """整张图若是「正文型」,返回它的文字;否则返回空串。

    只在**所有** foreignObject 都是正文型时才判定成立。混合插图(有图形
    又有文本框)不在这里降级,免得为了保住文字把图形丢掉——那种图仍走
    SVG 路径,正文部分由 _flatten_foreign_objects 尽量还原。
    """
    objects = _FOREIGN.findall(markup)
    if not objects or not all(_fo_is_flow(inner) for _, inner in objects):
        return ""
    return "\n\n".join(
        t for t in (_fo_flow_text(inner) for _, inner in objects) if t)


def _ensure_namespace(markup: str) -> str:
    """给根 <svg> 补上命名空间声明。

    LaTeXML 的内联 SVG 不写 xmlns——嵌在 HTML 里时浏览器按 HTML 规则
    自动把它放进 SVG 命名空间,所以原页面不需要。一旦抽成独立的 .svg 文件,
    缺了它浏览器就按「未知 XML」处理,渲染成空白。实测这些图全都没有。
    """
    m = re.match(r"<svg\b[^>]*>", markup)
    if not m or "xmlns=" in m.group(0):
        return markup
    tag = m.group(0)
    return f"<svg {SVG_NS}{tag[len('<svg'):]}" + markup[m.end():]


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
      _blocks  结果列表,kind 为 "p"/"table"/"verbatim"/"formula"/"image"/"svg",
               标题则为 "h2"–"h6"(级别由 heading_level() 判定)
      _skip    正在跳过的标签栈(遇到 </x> 弹出),用于忽略 script/参考文献等
      _buf     当前正在累积的文本;进入 <p>/<h*>/<figcaption>/<td> 时置空
               开始收集,遇到结束标签时 _flush() 收尾——这样标签内再嵌
               <span>、<b> 等行内标签也不受影响,文本自然接在一起。
      _table   正在收集的表格 {"rows": [[单元格,...]], "row": [...]}
               _table_depth 记录嵌套层数,只在最外层(depth==1)建结构,
               嵌套表的内容直接并入外层单元格文本,避免结构错乱。

    五类特殊处理:
      - <math> 用其 alttext 以 $...$ 形式内联,避免公式变成乱码
      - 跳过 script/style 与参考文献(ltx_bibliograph)
      - 插图有三条路:<img>/<object type="image/*"> 取 src 存 URL;
        <svg class="ltx_picture"> 没有 src,只能把标记原样存下来
        (见 _flush_svg 与 _svg_parts);若这张图其实是排版好的正文
        (prompt 模板之类),则降级成 verbatim 文本块。SVG 路径上还要把
        <foreignObject> 里的 HTML/MathML 文字转成原生 <text>,否则抽成
        独立文件后文字全丢(见 _flatten_foreign_objects)
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
        # 正在采集的内联插图标记(逐段拼回 <svg>...</svg>)。非 None 时
        # 所有事件都只服务于拼标记,不再产生任何文本块。
        self._svg_parts: list[str] | None = None
        self._svg_depth = 0
        self._svg_stack: list[str] = []   # 起始标签名(原大小写),用来配对结束标签
        self._svg_id = ""
        # 解析过程中见到过几张图(<img> 与 <object type="image/*"> 都算)。
        # parse_blocks 用它判断是否需要走正则兜底,比"结果里有没有 image 块"
        # 更准——表格内的图片是内联进单元格的,按结果判断会误触发兜底。
        # 内联 SVG 刻意不计入:它走的是自己的采集路径,不会出现「HTMLParser
        # 漏掉 <img>」那类问题,计进来反而会白白关掉兜底。
        self.graphic_count = 0

    def _skip_this(self, tag: str, attrs: dict) -> bool:
        """判断某标签子树是否整体不要(脚本/样式/参考文献/页面 UI 图标)。"""
        if tag in ("script", "style", "noscript"):
            return True
        if tag == "svg":
            # LaTeXML 把插图渲染成内联 <svg class="ltx_picture">,只认
            # <img>/<object> 会整片漏掉——实测 2201.11903 的 11 张图漏了 7 张。
            # 其余 <svg> 是页面 UI(role="presentation" 的导航/主题按钮),仍跳过。
            return PICTURE_CLASS not in attrs.get("class", "")
        # 参考文献整体跳过:正文里的 [12] 目前回溯不到条目,留着反而误导
        return "ltx_bibliograph" in attrs.get("class", "")

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)

        # 采集内联插图期间:原样拼回标记,不产生任何文本块。
        # 用 get_starttag_text() 拿原文,属性里的实体、引号风格都保持原样。
        if self._svg_parts is not None:
            raw = self.get_starttag_text()
            if tag in VOID_TAGS:
                # 空元素要补成自闭合,否则 XML 里没有结束标签可配
                self._svg_parts.append(_self_close(raw))
            else:
                self._svg_parts.append(raw)
                self._svg_stack.append(_start_name(raw))
            if tag == "svg":            # 嵌套 <svg>(LaTeXML 的子面板)
                self._svg_depth += 1
            return

        # 跳过判定放在最前面:script/svg/参考文献里的 <img> 也不该被收进来。
        if self._skip:  # 已在跳过中:嵌套的可跳过标签入栈,其余无视
            if self._skip_this(tag, a) or tag == "math":
                self._skip.append(tag)
            return
        if self._skip_this(tag, a):
            self._skip.append(tag)
            return

        # 内联插图:<svg class="ltx_picture"> 没有 src,得把标记本身存下来,
        # 由 services 层写成 .svg 文件(见 images.localize_images 的 inline-svg)。
        if tag == "svg" and PICTURE_CLASS in a.get("class", ""):
            if self._buf is not None:   # 图前的残段先结算,保持顺序
                self._flush()
            self._svg_id = a.get("id") or f"picture-{len(self.blocks)}"
            self._svg_parts = [self.get_starttag_text()]
            self._svg_depth = 1
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

    def handle_startendtag(self, tag, attrs):
        """自闭合标签(<path ... />)。

        默认实现会拆成 starttag + endtag 两次回调,采集内联插图时就会拼出
        `<path ... /></path>` 这种非法标记,所以这里单独处理:只记一次原文。
        """
        if self._svg_parts is not None:
            self._svg_parts.append(self.get_starttag_text())
            return
        super().handle_startendtag(tag, attrs)

    def handle_endtag(self, tag):
        if self._svg_parts is not None:   # 采集内联插图:补结束标签
            # 结束标签名用栈里存的原始大小写,不能用回调给的 tag(已被转小写)。
            for name in _close_names(self._svg_stack, tag):
                self._svg_parts.append(f"</{name}>")
            if tag == "svg":
                self._svg_depth -= 1
                if self._svg_depth <= 0:
                    self._flush_svg()
            return
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
        if self._svg_parts is not None:
            # convert_charrefs=True 已经把实体解码过了(&lt; → <),直接拼回去
            # 会拼出非法标记,也会让后面的剥标签逻辑把「<」当成真标签吃掉。
            # 重新转义一次才是忠实还原。
            self._svg_parts.append(html.escape(data, quote=False))
            return
        if self._skip or self._buf is None:
            return
        self._buf += data

    def _flush_svg(self):
        """内联插图采集完成,按内容分两条路出去。

        正文型插图(foreignObject 里是排版好的文本,如 prompt 模板)走
        ("verbatim", 文字):这类内容转成 <text> 既没法折行(几十个字符一行
        会横向溢出到框外),又会因为 _fo_plain 只取第一个 alttext 而把整块
        正文压成一个字符,当文本块给出反而完整、可选中、可翻译。

        普通插图走 ("svg", "名字\\t标记"),名字取 <svg id>(如 S3.F4.pic1),
        天然唯一且与来源对得上;services 层据此落成
        assets/<id>/inline/<名字>.svg。
        """
        parts = "".join(self._svg_parts or [])
        self._svg_parts, self._svg_depth, self._svg_stack = None, 0, []
        flow = _flow_text(parts)
        if flow:
            self.blocks.append(("verbatim", flow))
            return
        markup = _ensure_namespace(_flatten_foreign_objects(parts))
        name = sanitize(self._svg_id) or "picture"
        if markup:
            self.blocks.append(("svg", f"{name}\t{markup}"))

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
