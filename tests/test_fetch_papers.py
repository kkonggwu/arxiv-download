#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_papers.py 的回归测试(仅标准库,不联网)。

运行:
    python -m unittest discover -s tests -v
或:
    python tests/test_fetch_papers.py

覆盖两类曾经出过问题、且不依赖网络的行为:
  1. HTML 表格解析——早期版本会把 <table> 里的文字整段丢掉;
  2. 翻译缓存的失败语义——早期版本会把失败提示写进缓存,导致该段永不重试。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fetch_papers as fp  # noqa: E402

PARA = "This is a sufficiently long paragraph of English text for parsing."  # >40 字符


def wrap(body: str) -> str:
    """包一层论文正文容器,模拟 arXiv/ar5iv 的页面结构。"""
    return f'<div class="ltx_page_main">{body}</div><div class="ltx_page_footer">x</div>'


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
        blocks = fp.parse_blocks(html)
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
        table = [t for k, t in fp.parse_blocks(html) if k == "table"][0]
        self.assertEqual(table.splitlines()[0], "| a | b |")
        self.assertEqual(table.splitlines()[2], "| c | d |")

    def test_pipe_in_cell_is_escaped(self):
        html = wrap("<table><tr><td>a|b</td><td>c</td></tr></table>")
        table = [t for k, t in fp.parse_blocks(html) if k == "table"][0]
        self.assertIn(r"a\|b", table)

    def test_paragraph_inside_cell_does_not_split_cell(self):
        html = wrap("<table><tr><td><p>first part</p><p>second part</p></td>"
                    "<td>x</td></tr></table>")
        table = [t for k, t in fp.parse_blocks(html) if k == "table"][0]
        # 两段应合并进同一格(只有一行 → 表头 + 分隔行 = 2 行),
        # 而不是多出一行或一格;两段之间保留空格,不能粘连。
        self.assertEqual(len(table.splitlines()), 2)
        self.assertIn("first part second part", table.splitlines()[0])

    def test_figure_caption_kept_after_table(self):
        html = wrap("<figure><table><tr><td>a</td><td>b</td></tr></table>"
                    "<figcaption>Table 7: Ablation on the number of layers.</figcaption>"
                    "</figure>")
        blocks = fp.parse_blocks(html)
        self.assertEqual(blocks[-1][0], "p")
        self.assertTrue(blocks[-1][1].startswith("【图注】Table 7:"))

    def test_table_in_bibliography_is_skipped(self):
        html = wrap('<div class="ltx_bibliograph"><table>'
                    "<tr><td>should</td><td>not appear</td></tr></table></div>")
        self.assertEqual([t for k, t in fp.parse_blocks(html) if k == "table"], [])

    def test_render_table_pads_ragged_rows(self):
        md = fp.render_table([["a", "b", "c"], ["d"]])
        self.assertEqual(md.splitlines()[2], "| d |  |  |")

    def test_render_table_empty(self):
        self.assertEqual(fp.render_table([]), "")

    def test_single_column_table_becomes_code_block(self):
        # 单列表格多是 prompt 模板/清单,转代码块比套表头好读
        html = wrap("<table><tr><td>line one</td></tr>"
                    "<tr><td>line two</td></tr></table>")
        blocks = fp.parse_blocks(html)
        self.assertEqual([k for k, _ in blocks], ["verbatim"])
        self.assertEqual(blocks[0][1], "```\nline one\nline two\n```")

    def test_code_block_fence_grows_past_inner_backticks(self):
        html = wrap("<table><tr><td>a ``` b</td></tr></table>")
        code = [t for k, t in fp.parse_blocks(html) if k == "verbatim"][0]
        self.assertTrue(code.startswith("````\n"))
        self.assertTrue(code.endswith("\n````"))

    def test_single_column_keeps_pipe_unescaped(self):
        # 代码块里不应出现转义用的反斜杠
        html = wrap("<table><tr><td>a|b</td></tr></table>")
        code = [t for k, t in fp.parse_blocks(html) if k == "verbatim"][0]
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
        blocks = fp.parse_blocks(html)
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
        formulas = [t for k, t in fp.parse_blocks(html) if k == "formula"]
        self.assertEqual(formulas, ["a=1", "b=2"])


class TestBilingualCache(unittest.TestCase):
    """验证失败不落缓存、历史失败缓存会被清理并重试。"""

    PID = "1234.56789"
    HTML = wrap(f"<h2>Abstract</h2><p>{PARA}</p>"
                "<table><tr><td>1.5</td><td>2.5</td></tr></table>")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self._saved = {n: getattr(fp, n)
                       for n in ("BASE", "BILINGUAL_DIR", "CACHE_DIR", "REGISTRY")}
        fp.BASE = root
        fp.BILINGUAL_DIR = root / "双语"
        fp.CACHE_DIR = fp.BILINGUAL_DIR / ".cache"
        fp.REGISTRY = root / "papers.json"
        fp.CACHE_DIR.mkdir(parents=True)
        fp.REGISTRY.write_text('{"papers": []}', encoding="utf-8")
        self.reg = {"papers": [{"id": self.PID, "category": "测试",
                                "title": "A Test Paper"}]}

    def tearDown(self):
        for name, value in self._saved.items():
            setattr(fp, name, value)
        self.tmp.cleanup()

    def _run(self, translate):
        with mock.patch.object(fp, "fetch_paper_html",
                               return_value=(self.HTML, "test")), \
             mock.patch.object(fp, "translate_one", side_effect=translate), \
             mock.patch("time.sleep"):
            return fp.build_bilingual(self.PID, self.reg)

    def _cache(self):
        return json.loads(
            (fp.CACHE_DIR / f"{self.PID}.json").read_text(encoding="utf-8"))

    def test_failed_translation_is_not_persisted(self):
        out = self._run(RuntimeError("boom"))
        cache = self._cache()
        self.assertNotIn(PARA, cache)
        self.assertFalse([v for v in cache.values()
                          if isinstance(v, str) and v.startswith(fp.FAIL_MARK)])
        # 本次输出里仍要有可见的失败提示
        self.assertIn(fp.FAIL_MARK, out.read_text(encoding="utf-8"))

    def test_stale_failure_cache_is_pruned_and_retried(self):
        (fp.CACHE_DIR / f"{self.PID}.json").write_text(
            json.dumps({PARA: f"{fp.FAIL_MARK} 翻译失败: 旧记录"}),
            encoding="utf-8")
        out = self._run(lambda text: "【译文】")
        self.assertEqual(self._cache()[PARA], "【译文】")
        self.assertNotIn(fp.FAIL_MARK, out.read_text(encoding="utf-8"))

    def test_table_is_rendered_and_not_translated(self):
        out = self._run(lambda text: "【译文】")
        md = out.read_text(encoding="utf-8")
        self.assertIn("【表格】", md)
        self.assertIn("| 1.5 | 2.5 |", md)
        # 表格不应进入翻译缓存
        self.assertNotIn("| 1.5 | 2.5 |", self._cache())

    def test_successful_translation_is_cached(self):
        self._run(lambda text: "【译文】")
        self.assertEqual(self._cache()[PARA], "【译文】")


if __name__ == "__main__":
    unittest.main(verbosity=2)
