"""Markdown 渲染:标题级别、表格、代码块。

LaTeXML 用同一套 h1–h6 承载所有层级,靠 class 区分,不能只看标签号。
"""

import unittest

from paperkit.domain import heading_level, parse_blocks, render_code_block, render_table
from tests.helpers import bootstrap  # noqa: F401


class TestHeadingLevels(unittest.TestCase):
    def test_class_wins_over_tag_number(self):
        # Abstract 是 h6，但语义上就是一级章节，不能变成 ######
        self.assertEqual(
            heading_level("h6", {"class": "ltx_title ltx_title_abstract"}), 2)

    def test_subsection_and_deeper(self):
        self.assertEqual(
            heading_level("h3", {"class": "ltx_title ltx_title_subsection"}), 3)
        self.assertEqual(
            heading_level("h4", {"class": "ltx_title ltx_title_subsubsection"}), 4)
        self.assertEqual(
            heading_level("h5", {"class": "ltx_title ltx_title_paragraph"}), 5)

    def test_document_title_is_skipped(self):
        self.assertIsNone(
            heading_level("h1", {"class": "ltx_title ltx_title_document"}))

    def test_falls_back_to_tag_number(self):
        self.assertEqual(heading_level("h3", {}), 3)
        self.assertEqual(heading_level("h1", {}), 2)   # # 留给论文标题

    def test_levels_are_clamped_to_2_6(self):
        self.assertEqual(heading_level("h6", {}), 6)
        self.assertEqual(heading_level("h9", {}), 6)
        self.assertEqual(heading_level("h1", {}), 2)


class TestRenderTable(unittest.TestCase):
    def test_ragged_rows_are_padded(self):
        md = render_table([["a", "b", "c"], ["d"]])
        self.assertEqual(md.splitlines()[2], "| d |  |  |")

    def test_empty_rows_render_nothing(self):
        self.assertEqual(render_table([]), "")

    def test_first_row_becomes_header(self):
        md = render_table([["a", "b"], ["c", "d"]])
        self.assertEqual(md.splitlines()[0], "| a | b |")
        self.assertEqual(md.splitlines()[1], "| --- | --- |")


class TestRenderCodeBlock(unittest.TestCase):
    def test_fence_grows_past_inner_backticks(self):
        code = render_code_block([["a ``` b"]])
        self.assertTrue(code.startswith("````\n"))
        self.assertTrue(code.endswith("\n````"))

    def test_pipe_is_not_escaped_in_code_block(self):
        # 转义只发生在 render_table 里;代码块要保留原文
        self.assertIn("a|b", render_code_block([["a|b"]]))

    def test_empty_rows_render_nothing(self):
        self.assertEqual(render_code_block([]), "")
        self.assertEqual(render_code_block([[""], [""]]), "")


class TestHeadingBlocksInParser(unittest.TestCase):
    def test_parse_blocks_encodes_level_in_kind(self):
        html = ('<div class="ltx_page_main">'
                '<h2 class="ltx_title ltx_title_section">1 Introduction</h2>'
                '<h3 class="ltx_title ltx_title_subsection">1.1 Setup</h3>'
                '<h4 class="ltx_title ltx_title_subsubsection">1.1.1 Details</h4>'
                '<h1 class="ltx_title ltx_title_document">The Paper Title</h1>'
                "</div>")
        kinds = [k for k, _ in parse_blocks(html)]
        self.assertEqual(kinds, ["h2", "h3", "h4"])   # 文档标题被丢掉


if __name__ == "__main__":
    unittest.main(verbosity=2)
