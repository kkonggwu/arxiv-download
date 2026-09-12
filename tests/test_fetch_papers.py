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
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fetch_papers as fp  # noqa: E402
from paperkit.config import Settings  # noqa: E402

PARA = "This is a sufficiently long paragraph of English text for parsing."  # >40 字符


def wrap(body: str) -> str:
    """包一层论文正文容器,模拟 arXiv/ar5iv 的页面结构。"""
    return f'<div class="ltx_page_main">{body}</div><div class="ltx_page_footer">x</div>'


class TestLogging(unittest.TestCase):
    def test_log_replaces_unencodable_console_characters(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="gbk")
        with mock.patch.object(fp.sys, "stdout", stream):
            fp.log("✓ 已生成")
            stream.flush()
        self.assertEqual(stream.buffer.getvalue().decode("gbk").splitlines(), ["? 已生成"])


class TestAtomicWrites(unittest.TestCase):
    def test_write_text_atomic_replaces_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "state.json"
            target.write_text("old", encoding="utf-8")
            fp.write_text_atomic(target, "new")
            self.assertEqual(target.read_text(encoding="utf-8"), "new")
            self.assertFalse((Path(tmp) / "state.json.tmp").exists())


class TestSettings(unittest.TestCase):
    def test_cli_values_override_environment(self):
        with mock.patch.dict("os.environ", {
            "HTTPS_PROXY": "http://env-proxy",
            "TRANSLATE_BACKEND": "openai",
            "TRANSLATE_MODEL": "env-model",
        }, clear=False):
            settings = Settings.from_values(
                proxy="http://cli-proxy", translator="google", model="cli-model")
        self.assertEqual(settings.proxy, "http://cli-proxy")
        self.assertEqual(settings.translate_backend, "google")
        self.assertEqual(settings.openai_model, "cli-model")


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


class TestHeadingLevels(unittest.TestCase):
    """LaTeXML 用同一套 h1–h6 承载所有层级，靠 class 区分，不能只看标签号。"""

    def test_class_wins_over_tag_number(self):
        # Abstract 是 h6，但语义上就是一级章节，不能变成 ######
        self.assertEqual(
            fp.heading_level("h6", {"class": "ltx_title ltx_title_abstract"}), 2)

    def test_subsection_and_deeper(self):
        self.assertEqual(
            fp.heading_level("h3", {"class": "ltx_title ltx_title_subsection"}), 3)
        self.assertEqual(
            fp.heading_level("h4", {"class": "ltx_title ltx_title_subsubsection"}), 4)
        self.assertEqual(
            fp.heading_level("h5", {"class": "ltx_title ltx_title_paragraph"}), 5)

    def test_document_title_is_skipped(self):
        self.assertIsNone(
            fp.heading_level("h1", {"class": "ltx_title ltx_title_document"}))

    def test_falls_back_to_tag_number(self):
        self.assertEqual(fp.heading_level("h3", {}), 3)
        self.assertEqual(fp.heading_level("h1", {}), 2)   # # 留给论文标题

    def test_parse_blocks_encodes_level_in_kind(self):
        html = wrap('<h2 class="ltx_title ltx_title_section">1 Introduction</h2>'
                    '<h3 class="ltx_title ltx_title_subsection">1.1 Setup</h3>'
                    '<h4 class="ltx_title ltx_title_subsubsection">1.1.1 Details</h4>'
                    '<h1 class="ltx_title ltx_title_document">The Paper Title</h1>')
        kinds = [k for k, _ in fp.parse_blocks(html)]
        self.assertEqual(kinds, ["h2", "h3", "h4"])   # 文档标题被丢掉

    def test_bilingual_renders_nested_headings(self):
        html = wrap('<h2 class="ltx_title ltx_title_section">1 Introduction</h2>'
                    f"<p>{PARA}</p>"
                    '<h3 class="ltx_title ltx_title_subsection">1.1 Setup</h3>'
                    f"<p>{PARA}</p>")
        tmp = tempfile.TemporaryDirectory()
        saved = {n: getattr(fp, n) for n in ("BASE", "BILINGUAL_DIR", "CACHE_DIR",
                                             "REGISTRY")}
        try:
            root = Path(tmp.name)
            fp.BASE = root
            fp.BILINGUAL_DIR = root / "双语"
            fp.CACHE_DIR = fp.BILINGUAL_DIR / ".cache"
            fp.REGISTRY = root / "papers.json"
            fp.CACHE_DIR.mkdir(parents=True)
            fp.REGISTRY.write_text('{"papers": []}', encoding="utf-8")
            with mock.patch.object(fp, "fetch_paper_html",
                                   return_value=(html, "test", "https://x/")), \
                 mock.patch.object(fp, "translate_one",
                                   side_effect=lambda t: "译"), \
                 mock.patch("time.sleep"):
                out = fp.build_bilingual(
                    "1234.56789",
                    {"papers": [{"id": "1234.56789", "category": "测试",
                                 "title": "T"}]})
            md = out.read_text(encoding="utf-8")
        finally:
            for name, value in saved.items():
                setattr(fp, name, value)
            tmp.cleanup()
        self.assertIn("\n## 1 Introduction\n", md)
        self.assertIn("\n### 1.1 Setup\n", md)
        self.assertNotIn("\n## 1.1 Setup\n", md)


class TestImageExtraction(unittest.TestCase):
    """arXiv/ar5iv 用 LaTeXML 渲染,大多数插图是 <object data> 而不是 <img src>。"""

    def test_object_data_is_captured(self):
        html = wrap('<figure><object type="image/svg+xml" '
                    'data="2501.12948v2/plot.svg"></object>'
                    "<figcaption>Figure 1: A plot of something.</figcaption>"
                    "</figure>")
        imgs = [t for k, t in fp.parse_blocks(html) if k == "image"]
        self.assertEqual(imgs, ["2501.12948v2/plot.svg\t"])

    def test_img_src_still_captured_with_alt(self):
        html = wrap('<img src="a.png" alt="Refer to caption">')
        imgs = [t for k, t in fp.parse_blocks(html) if k == "image"]
        self.assertEqual(imgs, ["a.png\tRefer to caption"])

    def test_object_with_non_image_type_is_ignored(self):
        html = wrap('<object type="text/html" data="foo.html"></object>')
        self.assertEqual([k for k, _ in fp.parse_blocks(html)], [])

    def test_lazy_loading_attributes_are_supported(self):
        html = wrap('<img data-src="lazy.png">')
        imgs = [t for k, t in fp.parse_blocks(html) if k == "image"]
        self.assertEqual(imgs, ["lazy.png\t"])

    def test_image_inside_bibliography_is_skipped(self):
        html = wrap('<div class="ltx_bibliograph">'
                    '<object type="image/svg+xml" data="x.svg"></object></div>')
        self.assertEqual([k for k, _ in fp.parse_blocks(html)], [])

    def test_object_fallback_content_is_not_double_counted(self):
        # <object> 里可能带回退用的 <img>,同一张图不能收两遍
        html = wrap('<object type="image/svg+xml" data="real.svg">'
                    '<img src="fallback.png"></object>')
        imgs = [t for k, t in fp.parse_blocks(html) if k == "image"]
        self.assertEqual(imgs, ["real.svg\t"])


class TestImageLocalization(unittest.TestCase):
    """图片要落到 assets/ 并改成相对路径,离线也能看图。"""

    PID = "1234.56789"
    BASE = "https://arxiv.org/html/"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = {n: getattr(fp, n) for n in ("BASE", "BILINGUAL_DIR")}
        fp.BASE = Path(self.tmp.name)
        fp.BILINGUAL_DIR = fp.BASE / "双语"

    def tearDown(self):
        for name, value in self._saved.items():
            setattr(fp, name, value)
        self.tmp.cleanup()

    def _lines(self):
        return [f"![Refer to caption]({self.PID}v2/plot.svg)", ""]

    def test_relative_url_is_downloaded_and_rewritten(self):
        with mock.patch.object(fp, "http_get", return_value=b"<svg/>") as g:
            out = fp.localize_images(self._lines(), self.PID, self.BASE)
        self.assertEqual(out[0], f"![Refer to caption](../assets/{self.PID}/"
                                 f"{self.PID}v2/plot.svg)")
        dest = fp.BILINGUAL_DIR / "assets" / self.PID / f"{self.PID}v2" / "plot.svg"
        self.assertEqual(dest.read_bytes(), b"<svg/>")
        g.assert_called_once_with(f"https://arxiv.org/html/{self.PID}v2/plot.svg",
                                  timeout=60)

    def test_existing_file_is_reused_without_request(self):
        dest = fp.BILINGUAL_DIR / "assets" / self.PID / f"{self.PID}v2" / "plot.svg"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"<svg/>")
        with mock.patch.object(fp, "http_get") as g:
            out = fp.localize_images(self._lines(), self.PID, self.BASE)
        self.assertFalse(g.called)
        self.assertIn(f"../assets/{self.PID}/{self.PID}v2/plot.svg", out[0])

    def test_failure_falls_back_to_absolute_url(self):
        with mock.patch.object(fp, "http_get", side_effect=OSError("boom")):
            out = fp.localize_images(self._lines(), self.PID, self.BASE)
        self.assertIn(f"https://arxiv.org/html/{self.PID}v2/plot.svg", out[0])

    def test_html_response_is_rejected(self):
        with mock.patch.object(fp, "http_get", return_value=b"<!DOCTYPE html><html>"):
            out = fp.localize_images(self._lines(), self.PID, self.BASE)
        self.assertIn("https://arxiv.org", out[0])

    def test_absolute_url_is_left_alone(self):
        lines = ["![x](https://example.com/a.png)"]
        with mock.patch.object(fp, "http_get") as g:
            out = fp.localize_images(lines, self.PID, self.BASE)
        self.assertEqual(out, lines)
        self.assertFalse(g.called)

    def test_ar5iv_path_prefix_is_stripped(self):
        rel = fp._asset_relpath("https://ar5iv.labs.arxiv.org/html/1706.03762/"
                                "assets/x.svg")
        self.assertEqual(rel.as_posix(), "1706.03762/assets/x.svg")

    def test_fenced_code_block_is_not_rewritten(self):
        """代码块里是 prompt 模板原文，出现 ![](...) 字样也不能被改写。"""
        lines = ["```",
                 f"![not an image]({self.PID}v2/x.svg)",
                 "```",
                 f"![real]({self.PID}v2/plot.svg)"]
        with mock.patch.object(fp, "http_get", return_value=b"<svg/>"):
            out = fp.localize_images(lines, self.PID, self.BASE)
        self.assertEqual(out[1], f"![not an image]({self.PID}v2/x.svg)")
        self.assertIn("../assets/", out[3])

    def test_tilde_fence_is_also_respected(self):
        lines = ["~~~",
                 f"![x]({self.PID}v2/x.svg)",
                 "~~~"]
        with mock.patch.object(fp, "http_get") as g:
            out = fp.localize_images(lines, self.PID, self.BASE)
        self.assertFalse(g.called)
        self.assertEqual(out[1], f"![x]({self.PID}v2/x.svg)")

    def test_no_download_rewrites_to_absolute_url(self):
        with mock.patch.object(fp, "http_get") as g:
            out = fp.localize_images(self._lines(), self.PID, self.BASE,
                                     download=False)
        self.assertFalse(g.called)
        self.assertEqual(
            out[0],
            f"![Refer to caption](https://arxiv.org/html/{self.PID}v2/plot.svg)")
        self.assertFalse((fp.BILINGUAL_DIR / "assets").exists())


ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Attention Is All You Need</title>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <published>2017-06-12T17:57:34Z</published>
  </entry>
</feed>"""


class TestArxivIds(unittest.TestCase):
    def test_new_style(self):
        self.assertEqual(fp.parse_arxiv_id("2501.12948"), "2501.12948")
        self.assertEqual(fp.parse_arxiv_id("2501.12948v2"), "2501.12948")
        self.assertEqual(fp.parse_arxiv_id("  2501.12948  "), "2501.12948")

    def test_links(self):
        self.assertEqual(
            fp.parse_arxiv_id("https://arxiv.org/abs/2405.15793"), "2405.15793")
        self.assertEqual(
            fp.parse_arxiv_id("https://arxiv.org/pdf/2405.15793v1"), "2405.15793")

    def test_old_style(self):
        # 旧版 id 是 archive/YYMMNNN,2022 年以前的老论文都用这种
        self.assertEqual(fp.parse_arxiv_id("cs/0703045"), "cs/0703045")
        self.assertEqual(fp.parse_arxiv_id("hep-th/9901001"), "hep-th/9901001")
        self.assertEqual(fp.parse_arxiv_id("math.GT/0309136"), "math.GT/0309136")
        self.assertEqual(fp.parse_arxiv_id("cond-mat/0102536"), "cond-mat/0102536")

    def test_old_style_link(self):
        self.assertEqual(
            fp.parse_arxiv_id("https://arxiv.org/abs/cs/0703045"), "cs/0703045")

    def test_unrecognized(self):
        for bad in ("", "not-an-id", "2501", "1706.03762/extra", "cs/123"):
            self.assertIsNone(fp.parse_arxiv_id(bad), bad)


class TestMetadata(unittest.TestCase):
    """元数据取不到时不能把占位文件名固化进登记表。"""

    def test_success_parses_fields(self):
        with mock.patch.object(fp, "http_get", return_value=ATOM_XML.encode()):
            meta = fp.fetch_metadata("1706.03762")
        self.assertEqual(meta["title"], "Attention Is All You Need")
        self.assertEqual(meta["year"], "2017")
        self.assertEqual(meta["authors"], ["Ashish Vaswani", "Noam Shazeer"])

    def test_network_failure_returns_none(self):
        with mock.patch.object(fp, "http_get", side_effect=OSError("unreachable")):
            self.assertIsNone(fp.fetch_metadata("1706.03762"))

    def test_empty_title_returns_none(self):
        xml = ATOM_XML.replace("Attention Is All You Need", "")
        with mock.patch.object(fp, "http_get", return_value=xml.encode()):
            self.assertIsNone(fp.fetch_metadata("1706.03762"))

    def test_duplicate_authors_are_deduped_in_order(self):
        # arXiv API 实测会重复返回同一个作者(2501.12948 返回 200 个名字,
        # 其中两个各出现两次),按首次出现顺序去重
        xml = ATOM_XML.replace(
            "<author><name>Noam Shazeer</name></author>",
            "<author><name>Noam Shazeer</name></author>"
            "<author><name>Ashish Vaswani</name></author>"
            "<author><name>Noam Shazeer</name></author>")
        with mock.patch.object(fp, "http_get", return_value=xml.encode()):
            meta = fp.fetch_metadata("1706.03762")
        self.assertEqual(meta["authors"],
                         ["Ashish Vaswani", "Noam Shazeer"])

    def test_resolve_entry_omits_file_when_metadata_fails(self):
        with mock.patch.object(fp, "http_get", side_effect=OSError("boom")):
            entry = fp.resolve_entry("1706.03762", "经典")
        self.assertEqual(entry, {"id": "1706.03762", "category": "经典"})
        self.assertNotIn("file", entry)

    def test_resolve_entry_sets_file_when_metadata_ok(self):
        with mock.patch.object(fp, "http_get", return_value=ATOM_XML.encode()):
            entry = fp.resolve_entry("1706.03762", "经典")
        self.assertIn("file", entry)
        self.assertTrue(entry["file"].endswith("[1706.03762].pdf"))

    def test_ensure_metadata_leaves_entry_untouched_on_failure(self):
        entry = {"id": "1706.03762", "category": "经典"}
        with mock.patch.object(fp, "http_get", side_effect=OSError("boom")):
            self.assertFalse(fp.ensure_metadata(entry))
        self.assertEqual(entry, {"id": "1706.03762", "category": "经典"})

    def test_ensure_metadata_is_retried_after_failure(self):
        """核心回归:第一次失败后,第二次必须还会真的去拉元数据。"""
        entry = {"id": "1706.03762", "category": "经典"}
        with mock.patch.object(fp, "http_get", side_effect=OSError("boom")):
            self.assertFalse(fp.ensure_metadata(entry))
        self.assertNotIn("file", entry)      # 没被占位名污染

        with mock.patch.object(fp, "http_get",
                               return_value=ATOM_XML.encode()) as g:
            self.assertTrue(fp.ensure_metadata(entry))
        self.assertTrue(g.called)            # 确实重新请求了
        self.assertEqual(entry["title"], "Attention Is All You Need")
        self.assertTrue(entry["file"].endswith("[1706.03762].pdf"))


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
                               return_value=(self.HTML, "test",
                                             "https://example.test/html/")), \
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

    def test_cache_is_flushed_incrementally(self):
        """中途中断不该丢掉已翻好的部分——每 20 段要落盘一次。"""
        n = fp.CACHE_FLUSH_EVERY + 5
        html = wrap("".join(f"<p>{PARA} index {i} trailing filler</p>"
                            for i in range(n)))
        calls = {"n": 0}

        def flaky(text):
            calls["n"] += 1
            if calls["n"] > fp.CACHE_FLUSH_EVERY:
                raise KeyboardInterrupt          # 模拟 Ctrl-C
            return "【译文】"

        with mock.patch.object(fp, "fetch_paper_html",
                               return_value=(html, "test", "https://x/")), \
             mock.patch.object(fp, "translate_one", side_effect=flaky), \
             mock.patch("time.sleep"):
            with self.assertRaises(KeyboardInterrupt):
                fp.build_bilingual(self.PID, self.reg)

        self.assertEqual(len(self._cache()), fp.CACHE_FLUSH_EVERY)

    def test_nothing_retranslated_when_cache_is_warm(self):
        self._run(lambda text: "【译文】")
        with mock.patch.object(fp, "translate_one") as t:
            self._run(lambda text: "【译文】")
        self.assertFalse(t.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
