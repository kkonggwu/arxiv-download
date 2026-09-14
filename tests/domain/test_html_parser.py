"""HTML → 区块序列。表格三种走法 + 插图两种标签。

覆盖两类曾经出过问题的行为:
  1. 早期版本会把 <table> 里的文字整段丢掉;
  2. LaTeXML 的插图是 <object data> 而不是 <img src>,只认 <img> 会漏掉绝大多数图。
"""

import unittest

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
