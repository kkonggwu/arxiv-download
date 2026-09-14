"""HTML → 区块序列。表格三种走法 + 插图两种标签。

覆盖两类曾经出过问题的行为:
  1. 早期版本会把 <table> 里的文字整段丢掉;
  2. LaTeXML 的插图是 <object data> 而不是 <img src>,只认 <img> 会漏掉绝大多数图。
"""

import re
import unittest
import xml.etree.ElementTree as ET

from paperkit.domain import parse_blocks
from tests.helpers import PARA, bootstrap, wrap  # noqa: F401


class TestTableParsing(unittest.TestCase):
    def test_thead_table_becomes_markdown(self):
        html = wrap(
            "<h2>3 Experiments</h2>"
            f"<p>{PARA}</p>"
            '<figure class="ltx_table"><table>'
            "<thead><tr><th>Model</th><th>Params</th><th>Acc</th></tr></thead>"
            "<tbody>"
            "<tr><td>Baseline</td><td>7B</td><td>42.1</td></tr>"
            "<tr><td>Ours</td><td>7B</td><td>55.3</td></tr>"
            "</tbody></table>"
            "<figcaption>Table 1: Main results on the benchmark suite.</figcaption>"
            "</figure>"
            f"<p>{PARA}</p>"
        )
        blocks = parse_blocks(html)
        tables = [t for k, t in blocks if k == "table"]
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].splitlines()[0], "| Model | Params | Acc |")
        self.assertEqual(tables[0].splitlines()[1], "| --- | --- | --- |")
        self.assertIn("| Baseline | 7B | 42.1 |", tables[0])
        self.assertIn("| Ours | 7B | 55.3 |", tables[0])
        # 表格数据必须真的出现在结果里(这正是旧版的丢失点)
        self.assertIn("55.3", "\n".join(t for _, t in blocks))

    def test_table_without_th_uses_first_row_as_header(self):
        html = wrap("<table><tr><td>a</td><td>b</td></tr>"
                    "<tr><td>c</td><td>d</td></tr></table>")
        table = [t for k, t in parse_blocks(html) if k == "table"][0]
        self.assertEqual(table.splitlines()[0], "| a | b |")
        self.assertEqual(table.splitlines()[2], "| c | d |")

    def test_pipe_in_cell_is_escaped(self):
        html = wrap("<table><tr><td>a|b</td><td>c</td></tr></table>")
        table = [t for k, t in parse_blocks(html) if k == "table"][0]
        self.assertIn(r"a\|b", table)

    def test_paragraph_inside_cell_does_not_split_cell(self):
        html = wrap("<table><tr><td><p>first part</p><p>second part</p></td>"
                    "<td>x</td></tr></table>")
        table = [t for k, t in parse_blocks(html) if k == "table"][0]
        # 两段应合并进同一格(只有一行 → 表头 + 分隔行 = 2 行),
        # 而不是多出一行或一格;两段之间保留空格,不能粘连。
        self.assertEqual(len(table.splitlines()), 2)
        self.assertIn("first part second part", table.splitlines()[0])

    def test_figure_caption_kept_after_table(self):
        html = wrap("<figure><table><tr><td>a</td><td>b</td></tr></table>"
                    "<figcaption>Table 7: Ablation on the number of layers.</figcaption>"
                    "</figure>")
        blocks = parse_blocks(html)
        self.assertEqual(blocks[-1][0], "p")
        self.assertTrue(blocks[-1][1].startswith("【图注】Table 7:"))

    def test_table_in_bibliography_is_skipped(self):
        html = wrap('<div class="ltx_bibliograph"><table>'
                    "<tr><td>should</td><td>not appear</td></tr></table></div>")
        self.assertEqual([t for k, t in parse_blocks(html) if k == "table"], [])

    def test_single_column_table_becomes_code_block(self):
        # 单列表格多是 prompt 模板/清单,转代码块比套表头好读
        html = wrap("<table><tr><td>line one</td></tr>"
                    "<tr><td>line two</td></tr></table>")
        blocks = parse_blocks(html)
        self.assertEqual([k for k, _ in blocks], ["verbatim"])
        self.assertEqual(blocks[0][1], "```\nline one\nline two\n```")

    def test_single_column_keeps_pipe_unescaped(self):
        # 代码块里不应出现转义用的反斜杠
        html = wrap("<table><tr><td>a|b</td></tr></table>")
        code = [t for k, t in parse_blocks(html) if k == "verbatim"][0]
        self.assertIn("a|b", code)
        self.assertNotIn("\\|", code)

    def test_equation_table_becomes_formula(self):
        # LaTeXML 用 <table class="ltx_eqn_table"> 包行间公式,不能当表格
        html = wrap(
            '<table id="S2.E1" class="ltx_equation ltx_eqn_table"><tbody>'
            '<tr class="ltx_equation ltx_eqn_row">'
            '<td class="ltx_eqn_cell ltx_eqn_center_padleft"></td>'
            '<td class="ltx_eqn_cell ltx_align_center">'
            '<math alttext="E = mc^{2}"><span>E</span></math></td>'
            '<td class="ltx_eqn_cell ltx_eqn_eqno">(1)</td>'
            "</tr></tbody></table>"
        )
        blocks = parse_blocks(html)
        self.assertEqual([k for k, _ in blocks], ["formula"])
        # 公式表格里的 math 不再包 $...$,交由外层统一加 $$(否则会嵌套)
        self.assertEqual(blocks[0][1], "E = mc^{2}")

    def test_equation_group_yields_one_formula_per_row(self):
        html = wrap(
            '<table class="ltx_equationgroup ltx_eqn_align ltx_eqn_table"><tbody>'
            '<tr><td class="ltx_eqn_cell">'
            '<math alttext="a=1"></math></td><td>(1)</td></tr>'
            '<tr><td class="ltx_eqn_cell">'
            '<math alttext="b=2"></math></td><td>(2)</td></tr>'
            "</tbody></table>"
        )
        formulas = [t for k, t in parse_blocks(html) if k == "formula"]
        self.assertEqual(formulas, ["a=1", "b=2"])


class TestImageExtraction(unittest.TestCase):
    """arXiv/ar5iv 用 LaTeXML 渲染,大多数插图是 <object data> 而不是 <img src>。"""

    def test_object_data_is_captured(self):
        html = wrap('<figure><object type="image/svg+xml" '
                    'data="2501.12948v2/plot.svg"></object>'
                    "<figcaption>Figure 1: A plot of something.</figcaption>"
                    "</figure>")
        imgs = [t for k, t in parse_blocks(html) if k == "image"]
        self.assertEqual(imgs, ["2501.12948v2/plot.svg\t"])

    def test_img_src_still_captured_with_alt(self):
        html = wrap('<img src="a.png" alt="Refer to caption">')
        imgs = [t for k, t in parse_blocks(html) if k == "image"]
        self.assertEqual(imgs, ["a.png\tRefer to caption"])

    def test_object_with_non_image_type_is_ignored(self):
        html = wrap('<object type="text/html" data="foo.html"></object>')
        self.assertEqual([k for k, _ in parse_blocks(html)], [])

    def test_lazy_loading_attributes_are_supported(self):
        html = wrap('<img data-src="lazy.png">')
        imgs = [t for k, t in parse_blocks(html) if k == "image"]
        self.assertEqual(imgs, ["lazy.png\t"])

    def test_image_inside_bibliography_is_skipped(self):
        html = wrap('<div class="ltx_bibliograph">'
                    '<object type="image/svg+xml" data="x.svg"></object></div>')
        self.assertEqual([k for k, _ in parse_blocks(html)], [])

    def test_object_fallback_content_is_not_double_counted(self):
        # <object> 里可能带回退用的 <img>,同一张图不能收两遍
        html = wrap('<object type="image/svg+xml" data="real.svg">'
                    '<img src="fallback.png"></object>')
        imgs = [t for k, t in parse_blocks(html) if k == "image"]
        self.assertEqual(imgs, ["real.svg\t"])


class TestInlineSvgFigures(unittest.TestCase):
    """LaTeXML 把一部分插图直接内联成 <svg class="ltx_picture">。

    这类图没有 src,早期版本把它们整片跳过——实测 2201.11903 的 11 张图
    只抓到 4 张,漏掉的 7 张全是这种。这里把标记原样存下来交给 services 层落盘。
    """

    PIC = ('<svg id="S3.F4.pic1" class="ltx_picture ltx_centering" '
           'viewBox="0 0 10 10"><g><path d="M 0 0 L 1 1"></path></g></svg>')

    def _svgs(self, html):
        return [t for k, t in parse_blocks(html) if k == "svg"]

    def test_picture_svg_is_captured_with_its_markup(self):
        blocks = self._svgs(wrap(f"<figure>{self.PIC}</figure>"))
        self.assertEqual(len(blocks), 1)
        name, _, markup = blocks[0].partition("\t")
        self.assertEqual(name, "S3.F4.pic1")
        self.assertTrue(markup.startswith("<svg "))
        self.assertIn('id="S3.F4.pic1"', markup)
        self.assertTrue(markup.endswith("</svg>"))
        self.assertIn('<path d="M 0 0 L 1 1"></path>', markup)

    def test_markup_is_rebuilt_verbatim(self):
        # 属性原样保留,拼出来的标记必须能当独立 .svg 文件用
        blocks = self._svgs(wrap(f"<figure>{self.PIC}</figure>"))
        markup = blocks[0].partition("\t")[2]
        self.assertIn('class="ltx_picture ltx_centering"', markup)
        self.assertIn('viewBox="0 0 10 10"', markup)
        self.assertEqual(markup.count("<svg"), markup.count("</svg>"))

    def test_self_closing_child_does_not_gain_a_stray_end_tag(self):
        # 默认的 handle_startendtag 会拆成 start+end 两次回调,
        # 那样就会拼出 <path ... /></path> 这种非法标记
        html = wrap('<figure><svg id="p" class="ltx_picture">'
                    '<path d="M0 0"/><circle r="1"/></svg></figure>')
        markup = self._svgs(html)[0].partition("\t")[2]
        self.assertIn("<path d=\"M0 0\"/>", markup)
        self.assertNotIn("</path>", markup)
        self.assertNotIn("</circle>", markup)

    def test_page_ui_svg_is_still_skipped(self):
        # 页头的导航/主题按钮也是 <svg>,收进来就是垃圾
        html = wrap('<a class="header-button toggle-icon">'
                    '<svg role="presentation" height="1.25rem">'
                    '<path d="M0 0"/></svg></a>'
                    f"<p>{PARA}</p>")
        self.assertEqual(self._svgs(html), [])
        self.assertEqual([k for k, _ in parse_blocks(html)], ["p"])

    def test_svg_without_class_is_skipped(self):
        html = wrap('<svg viewBox="0 0 1 1"><path d="M0 0"/></svg>')
        self.assertEqual(self._svgs(html), [])

    def test_nested_svg_is_kept_whole(self):
        html = wrap('<figure><svg id="outer" class="ltx_picture">'
                    '<svg id="inner"><rect/></svg></svg></figure>')
        blocks = self._svgs(html)
        self.assertEqual(len(blocks), 1)          # 嵌套的算同一张图
        markup = blocks[0].partition("\t")[2]
        self.assertIn('<svg id="inner">', markup)
        self.assertEqual(markup.count("</svg>"), 2)

    def test_multiple_panels_stay_separate_in_order(self):
        # 2201.11903 的 Figure 4 由三个面板拼成,顺序不能乱
        html = wrap("<figure>"
                    + "".join(f'<svg id="S3.F4.pic{i}" class="ltx_picture"/>'
                              for i in (1, 2, 3))
                    + "<figcaption>Figure 4: A three-panel figure.</figcaption>"
                    "</figure>")
        blocks = parse_blocks(html)
        self.assertEqual([k for k, _ in blocks], ["svg", "svg", "svg", "p"])
        names = [t.partition("\t")[0] for k, t in blocks if k == "svg"]
        self.assertEqual(names, ["S3.F4.pic1", "S3.F4.pic2", "S3.F4.pic3"])
        self.assertTrue(blocks[-1][1].startswith("【图注】"))

    def test_url_images_and_inline_svgs_interleave_in_document_order(self):
        html = wrap("<figure><img src=\"a.png\"></figure>"
                    f"<figure>{self.PIC}</figure>"
                    '<figure><object type="image/svg+xml" data="b.svg"></object></figure>')
        self.assertEqual([k for k, _ in parse_blocks(html)],
                         ["image", "svg", "image"])

    def test_svg_inside_bibliography_is_skipped(self):
        html = wrap('<div class="ltx_bibliograph">'
                    '<svg id="x" class="ltx_picture"><path/></svg></div>')
        self.assertEqual(self._svgs(html), [])

    def test_svg_without_id_gets_a_fallback_name(self):
        html = wrap('<figure><svg class="ltx_picture"><path/></svg></figure>')
        name = self._svgs(html)[0].partition("\t")[0]
        self.assertTrue(name)

    def test_text_nodes_inside_svg_do_not_leak_into_paragraphs(self):
        html = wrap('<figure><svg id="p" class="ltx_picture">'
                    "<title>a label</title></svg></figure>")
        self.assertEqual([k for k, _ in parse_blocks(html)], ["svg"])


    def test_camel_case_tags_keep_their_case(self):
        """SVG 是大小写敏感的,而 HTMLParser 会把标签名转小写。

        实测 2201.11903 的 10 张内联图全部中招:<foreignObject>/<clipPath>
        的结束标签被拼成 </foreignobject>,产物是非法 XML,浏览器渲染不出来。
        """
        html = wrap('<figure><svg id="p" class="ltx_picture">'
                    '<defs><clipPath id="c"><path d="M0 0"/></clipPath>'
                    '<linearGradient id="g"><stop/></linearGradient></defs>'
                    '<textPath href="#c">x</textPath></svg></figure>')
        markup = self._svgs(html)[0].partition("\t")[2]
        self.assertIn("</clipPath>", markup)
        self.assertIn("</linearGradient>", markup)
        self.assertIn("</textPath>", markup)
        for bad in ("</clippath>", "</lineargradient>", "</textpath>"):
            self.assertNotIn(bad, markup)

    def test_rebuilt_markup_is_well_formed_xml(self):
        """最强的一条:拼出来的东西必须真的能当 .svg 文件解析。

        上面的用例都只断言片段,漏掉了「整体不合法」这类问题——
        大小写不匹配正是这样漏过去的。
        """
        html = wrap('<figure><svg id="p" class="ltx_picture" viewBox="0 0 9 9">'
                    '<defs><clipPath id="c"><path d="M0 0"/></clipPath></defs>'
                    '<g><foreignObject width="1" height="1">'
                    "<span>label</span></foreignObject></g>"
                    '<use href="#c"/></svg></figure>')
        markup = self._svgs(html)[0].partition("\t")[2]
        root = ET.fromstring(markup)          # 不合法会直接抛异常
        self.assertTrue(root.tag.endswith("svg"))
        self.assertEqual(root.get("viewBox"), "0 0 9 9")

    def test_svg_namespace_is_added_for_standalone_files(self):
        """LaTeXML 的内联图不带 xmlns(嵌在 HTML 里不需要)。

        抽成独立 .svg 后缺了它浏览器就按未知 XML 处理、渲染成空白,
        所以必须补上。
        """
        html = wrap('<figure><svg id="p" class="ltx_picture">'
                    '<path d="M0 0"/></svg></figure>')
        markup = self._svgs(html)[0].partition("\t")[2]
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', markup)
        self.assertTrue(markup.startswith('<svg xmlns="http://www.w3.org/2000/svg"'))
        # 补了之后仍然合法,而且原有属性一个不少
        root = ET.fromstring(markup)
        self.assertEqual(root.get("id"), "p")
        self.assertEqual(root.get("class"), "ltx_picture")

    def test_existing_namespace_is_not_duplicated(self):
        html = wrap('<figure><svg id="p" class="ltx_picture" '
                    'xmlns="http://www.w3.org/2000/svg"><path/></svg></figure>')
        markup = self._svgs(html)[0].partition("\t")[2]
        self.assertEqual(markup.count("xmlns="), 1)


class TestForeignObjectFlattening(unittest.TestCase):
    """foreignObject 必须转成原生 <text>,否则图上的文字全丢。

    SVG 被 <img> 引用时浏览器进入「安全静态模式」,foreignObject 内容一律
    不渲染。实测 2201.11903 的 10 张内联图抽成文件后,刻度、图例、标题
    全部消失,只剩光秃秃的曲线——图形对但读不懂。
    """

    FO_MATH = ('<foreignObject style="--ltx-fo-width:1em;font-size:8.5pt;" '
               'height="7.13" transform="matrix(1 0 0 -1 0 7.13)" width="5.88">'
               '<span class="ltx_foreignobject_container">'
               '<span class="ltx_foreignobject_content">'
               '<math id="m1" alttext="20"><semantics><mn>20</mn></semantics>'
               "</math></span></span></foreignObject>")

    FO_TEXT = ('<foreignObject style="--ltx-fo-width:3.5em;font-size:9.25pt;" '
               'height="8.51" transform="matrix(1 0 0 -1 0 8.51)" width="45.2">'
               '<span class="ltx_foreignobject_container">'
               '<span class="ltx_foreignobject_content">'
               '<span class="ltx_text">Solve rate (%)</span>'
               "</span></span></foreignObject>")

    def _markup(self, *fos):
        html = wrap('<figure><svg id="p" class="ltx_picture">'
                    + "".join(fos) + "</svg></figure>")
        return [t for k, t in parse_blocks(html) if k == "svg"][0].partition("\t")[2]

    def test_foreign_object_is_replaced_by_text(self):
        markup = self._markup(self.FO_MATH)
        self.assertNotIn("foreignObject", markup)
        self.assertIn(">20</text>", markup)

    def test_math_alttext_is_preferred_over_nested_markup(self):
        markup = self._markup(self.FO_MATH)
        self.assertIn(">20</text>", markup)
        self.assertNotIn("<mn>", markup)

    def test_plain_span_text_is_used(self):
        self.assertIn(">Solve rate (%)</text>", self._markup(self.FO_TEXT))

    def test_flip_transform_is_kept_so_glyphs_are_upright(self):
        """祖先 <g> 有垂直翻转,foreignObject 靠自身的翻转抵消。

        换成 <text> 时必须保留同一个 transform,否则整片文字会倒过来
        (实测第一版就是这样,标题读成了反的)。
        """
        markup = self._markup(self.FO_MATH)
        self.assertIn('transform="matrix(1 0 0 -1 0 7.13)"', markup)

    def test_baseline_offset_follows_the_calibrated_ratio(self):
        # 基线 = 翻转平移量 + 0.6 × 字号,0.6 是像素级标定出来的
        markup = self._markup(self.FO_MATH)
        self.assertIn('y="12.23"', markup)          # 7.13 + 0.6*8.5

    def test_font_size_is_carried_over(self):
        markup = self._markup(self.FO_TEXT)
        self.assertIn('font-size="9.25pt"', markup)
        self.assertIn('y="14.06"', markup)          # 8.51 + 0.6*9.25

    def test_inner_font_size_percentage_is_applied(self):
        """内层 span 常带 font-size:90%/80% 的二次缩放。

        漏掉它文字会整体偏大,密排的刻度和图例就叠在一起。
        """
        fo = ('<foreignObject style="font-size:9.25pt;" '
              'transform="matrix(1 0 0 -1 0 8.51)">'
              '<span class="ltx_text" style="font-size:90%;">Solve rate (%)</span>'
              "</foreignObject>")
        markup = self._markup(fo)
        self.assertIn('font-size="8.325pt"', markup)      # 9.25 × 0.9
        y = float(re.search(r'y="([\d.]+)"', markup).group(1))
        self.assertAlmostEqual(y, 8.51 + 0.6 * 8.325, places=1)

    def test_inner_font_size_80_percent_is_applied(self):
        fo = ('<foreignObject style="font-size:10pt;" '
              'transform="matrix(1 0 0 -1 0 10)">'
              '<span class="ltx_text" style="font-size:80%;">LaMDA</span>'
              "</foreignObject>")
        self.assertIn('font-size="8pt"', self._markup(fo))

    def test_object_without_position_is_dropped_not_misplaced(self):
        # 取不到 transform/字号就不放,免得文字飘到错误的位置上
        html = wrap('<figure><svg id="p" class="ltx_picture">'
                    "<foreignObject><span>lost</span></foreignObject>"
                    "</svg></figure>")
        markup = [t for k, t in parse_blocks(html) if k == "svg"][0].partition("\t")[2]
        self.assertNotIn("lost", markup)
        self.assertNotIn("foreignObject", markup)

    def test_result_is_still_well_formed_xml(self):
        markup = self._markup(self.FO_MATH, self.FO_TEXT)
        root = ET.fromstring(markup)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertEqual(len(root.findall(".//{http://www.w3.org/2000/svg}text")), 2)

    def test_special_characters_in_labels_are_escaped(self):
        fo = ('<foreignObject style="font-size:9pt;" transform="matrix(1 0 0 -1 0 9)"'
              '><span class="ltx_text">a &amp; b &lt;c&gt;</span></foreignObject>')
        markup = self._markup(fo)
        self.assertIn(">a &amp; b &lt;c&gt;</text>", markup)
        ET.fromstring(markup)          # 转义错了这里就会炸


class TestPictureMarkupRobustness(unittest.TestCase):
    """采集内联插图时,结束标签的大小写必须与起始标签严格配对。

    HTMLParser 把标签名转小写后才交给回调,所以结束标签的大小写只能靠栈里
    记的原文还原。栈一旦被搅乱,还原就失败,拼出 </clippath> 这种小写闭合
    标签——SVG 是大小写敏感的,整份 .svg 就成了非法 XML。实测 2501.12948 的
    A2.SS2.p1.pic1 就是这么坏的,而当时测试全绿。

    这里用 clipPath 做探针:foreignObject 会被扁平化掉,看不出大小写对不对;
    clipPath / linearGradient 这类驼峰元素会原样留在产物里,是唯一能验证的
    观测点。
    """

    def _markup(self, body):
        html = wrap('<figure><svg id="p" class="ltx_picture">'
                    + body + "</svg></figure>")
        return [t for k, t in parse_blocks(html) if k == "svg"][0].partition("\t")[2]

    def test_void_element_does_not_lowercase_the_next_close_tag(self):
        # <br> 是空元素,没有结束标签。它压在栈顶时会挡住后面 </clipPath> 的
        # 配对,把它退化成 </clippath>。实测里出现的是 <br class="ltx_break">。
        markup = self._markup('<clipPath id="c"><br class="ltx_break">'
                              "<rect/></clipPath>")
        self.assertIn("</clipPath>", markup)
        self.assertNotIn("</clippath>", markup)
        ET.fromstring(markup)          # 大小写配错这里就会炸

    def test_img_void_element_does_not_break_pairing(self):
        markup = self._markup('<clipPath id="c"><img src="y.png">'
                              "<rect/></clipPath>")
        self.assertIn("</clipPath>", markup)
        ET.fromstring(markup)

    def test_unclosed_trailing_element_does_not_break_pairing(self):
        # LaTeXML 常有未闭合的 <span>。它压在栈顶时不能只看栈顶,要往下找到
        # 真正的 clipPath,并把它上面的元素视为隐含闭合。
        markup = self._markup('<clipPath id="c"><span>dangling</clipPath>')
        self.assertIn("</clipPath>", markup)
        self.assertNotIn("</clippath>", markup)
        ET.fromstring(markup)

    def test_linear_gradient_keeps_its_case_too(self):
        markup = self._markup(
            '<linearGradient id="g"><br><stop offset="0"/></linearGradient>')
        self.assertIn("</linearGradient>", markup)
        self.assertNotIn("</lineargradient>", markup)
        ET.fromstring(markup)

    def test_void_element_is_emitted_self_closed(self):
        # HTML 写法 <br> 在 XML 里没有结束标签,后面所有标签都会被当成它的
        # 子节点,整份 .svg 报 mismatched tag。补成 <br/> 才合法。
        markup = self._markup('<br class="ltx_break"><rect/>')
        self.assertIn('<br class="ltx_break"/>', markup)
        ET.fromstring(markup)

    def test_already_self_closed_void_element_is_left_alone(self):
        markup = self._markup('<br class="ltx_break"/>')
        self.assertIn('<br class="ltx_break"/>', markup)
        self.assertNotIn("/></br>", markup)

    def test_unclosed_element_gets_an_implicit_close_tag(self):
        # <span> 没闭合时补上 </span>,否则会留下 <span>x</clipPath> 这种
        # 缺结束标签的非法标记
        markup = self._markup('<clipPath id="c"><span>dangling</clipPath>')
        self.assertIn("</span></clipPath>", markup)
        ET.fromstring(markup)


class TestFlowTextPictures(unittest.TestCase):
    """有些「图」其实是排版好的正文——prompt 模板、清单、算法伪码。

    实测 2501.12948 的 A2.SS2.p1.pic1:一个 foreignObject 里装了 7 段共
    1729 字的提示词模板。这类内容不能按图形处理:

      * 转成 <text> 没法折行,一行几十上百字符会横向溢出到框外;
      * _fo_plain 只取第一个 alttext,整块正文会被压成一个 "\\gg"。

    所以判定为正文图时降级成 verbatim 文本块——完整、可选中、可翻译。
    """

    TEMPLATE = (
        '<foreignObject style="--ltx-fo-width:44.07em;font-size:10pt;"'
        ' transform="matrix(1 0 0 -1 0 391.51)" width="609.8" height="394.97">'
        '<span class="ltx_foreignobject_container">'
        '<span class="ltx_foreignobject_content">'
        '<span class="ltx_inline-block ltx_minipage" style="width:44.07em;">'
        '<span class="ltx_p"><span class="ltx_text">'
        "Please act as an impartial judge and evaluate the quality of the "
        "responses provided by two AI assistants to the user prompt below. "
        "Begin your evaluation by generating your own answer to the prompt, "
        "and provide it before judging any of the candidate answers."
        '<br class="ltx_break">Assistant A is significantly better: '
        '[[A<math alttext="\\gg"><semantics><mo>\u226b</mo>'
        '<annotation encoding="application/x-tex">\\gg</annotation>'
        "</semantics></math>B]]"
        "</span></span></span></span></foreignObject>")

    SHORT_BLOCK = (
        '<foreignObject style="font-size:9pt;"'
        ' transform="matrix(1 0 0 -1 0 9)" width="30" height="9">'
        '<span class="ltx_inline-block ltx_minipage">'
        '<span class="ltx_p"><span class="ltx_text">too short to be prose'
        "</span></span></span></foreignObject>")

    LEGEND = ('<foreignObject style="font-size:9pt;"'
              ' transform="matrix(1 0 0 -1 0 9)" width="30" height="9">'
              '<span class="ltx_text">first<br class="ltx_break">second</span>'
              "</foreignObject>")

    def _blocks(self, body):
        return parse_blocks(wrap('<figure><svg id="p" class="ltx_picture">'
                                 + body + "</svg></figure>"))

    def test_prompt_template_becomes_a_verbatim_block(self):
        kinds = [k for k, _ in self._blocks(self.TEMPLATE)]
        self.assertEqual(kinds, ["verbatim"])

    def test_flow_text_keeps_every_line(self):
        text = [t for k, t in self._blocks(self.TEMPLATE) if k == "verbatim"][0]
        self.assertIn("Please act as an impartial judge", text)
        self.assertIn("Assistant A is significantly better", text)
        self.assertEqual(text.count("\n"), 1)      # 一个 <br> 断成两行

    def test_inline_math_shows_as_a_glyph_not_latex_source(self):
        text = [t for k, t in self._blocks(self.TEMPLATE) if k == "verbatim"][0]
        self.assertIn("\u226b", text)
        self.assertNotIn("\\gg", text)             # 别把 LaTeX 源码漏给读者

    def test_flow_text_carries_no_svg_markup(self):
        text = [t for k, t in self._blocks(self.TEMPLATE) if k == "verbatim"][0]
        for junk in ("<span", "<br", "foreignObject", "ltx_"):
            self.assertNotIn(junk, text)

    def test_chart_labels_still_produce_an_svg(self):
        # 只有单行标签、文字量很小,是普通插图,不能误判成正文
        kinds = [k for k, _ in self._blocks(self.LEGEND)]
        self.assertEqual(kinds, ["svg"])

    def test_short_text_block_stays_an_svg(self):
        # 有 minipage 结构但文字太少,说明它只是图里的附属说明
        kinds = [k for k, _ in self._blocks(self.SHORT_BLOCK)]
        self.assertEqual(kinds, ["svg"])

    def test_mixed_picture_is_not_downgraded(self):
        # 一张图里既有图形标签又有正文块时,不整体降级,否则图形会丢
        kinds = [k for k, _ in self._blocks(self.TEMPLATE + self.LEGEND)]
        self.assertEqual(kinds, ["svg"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
