"""生成中英对照材料:缓存语义、表格与标题渲染。

这里验证两条曾经出过问题的行为:
  1. 失败不落缓存(否则该段永远不再重试);
  2. 缓存增量落盘(中断不丢已翻好的部分)。
"""

import json
import tempfile
import unittest
from unittest import mock

from paperkit.services import bilingual
from paperkit.services.bilingual import build_bilingual
from tests.helpers import (  # noqa: F401
    PARA,
    FakeTranslator,
    bootstrap,
    echo_translator,
    failing_translator,
    make_settings,
    wrap,
)

PID = "1234.56789"


class TestBilingualRendering(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = make_settings(self.tmp.name)
        self.reg = {"papers": [{"id": PID, "category": "测试",
                                "title": "A Test Paper"}]}

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, html, translator=None):
        translator = translator or echo_translator()
        with mock.patch.object(bilingual, "fetch_paper_html",
                               return_value=(html, "test", "https://x/")), \
             mock.patch("time.sleep"):
            return build_bilingual(PID, self.reg, self.settings,
                                   translator=translator)

    def _cache(self):
        return json.loads(
            self.settings.cache_file(PID).read_text(encoding="utf-8"))

    def test_nested_heading_levels_are_preserved(self):
        html = wrap('<h2 class="ltx_title ltx_title_section">1 Introduction</h2>'
                    f"<p>{PARA}</p>"
                    '<h3 class="ltx_title ltx_title_subsection">1.1 Setup</h3>'
                    f"<p>{PARA}</p>")
        md = self._run(html).read_text(encoding="utf-8")
        self.assertIn("\n## 1 Introduction\n", md)
        self.assertIn("\n### 1.1 Setup\n", md)
        self.assertNotIn("\n## 1.1 Setup\n", md)

    def test_table_is_rendered_and_not_translated(self):
        html = wrap(f"<h2>Abstract</h2><p>{PARA}</p>"
                    "<table><tr><td>1.5</td><td>2.5</td></tr></table>")
        out = self._run(html)
        md = out.read_text(encoding="utf-8")
        self.assertIn("【表格】", md)
        self.assertIn("| 1.5 | 2.5 |", md)
        # 表格不参与翻译,也就不该进缓存
        self.assertNotIn("| 1.5 | 2.5 |", self._cache())

    def test_verbatim_block_is_kept(self):
        html = wrap(f"<h2>Prompt</h2><p>{PARA}</p>"
                    "<table><tr><td>line one</td></tr>"
                    "<tr><td>line two</td></tr></table>")
        md = self._run(html).read_text(encoding="utf-8")
        self.assertIn("【原文块】", md)
        self.assertIn("```\nline one\nline two\n```", md)

    def test_formula_is_rendered_as_display_math(self):
        html = wrap(f"<p>{PARA}</p>"
                    '<table class="ltx_eqn_table"><tbody><tr>'
                    '<td><math alttext="E = mc^{2}"></math></td>'
                    "</tr></tbody></table>")
        md = self._run(html).read_text(encoding="utf-8")
        self.assertIn("$$\nE = mc^{2}\n$$", md)

    def test_registry_records_the_output_path(self):
        self._run(wrap(f"<p>{PARA}</p>"))
        self.assertIn("bilingual", self.reg["papers"][0])
        # 落盘后 --list 才显示得出 ◈
        saved = json.loads(
            self.settings.registry_path.read_text(encoding="utf-8"))
        self.assertIn("bilingual", saved["papers"][0])

    def test_out_of_registry_paper_is_registered_automatically(self):
        html = wrap(f"<p>{PARA}</p>")
        with mock.patch.object(bilingual, "fetch_paper_html",
                               return_value=(html, "test", "https://x/")), \
             mock.patch.object(bilingual, "fetch_metadata",
                               return_value={"id": "9999.99999",
                                             "title": "New", "year": "2025",
                                             "authors": []}), \
             mock.patch("time.sleep"):
            build_bilingual("9999.99999", self.reg, self.settings,
                            translator=echo_translator())
        self.assertIn("9999.99999", [p["id"] for p in self.reg["papers"]])


class TestBilingualCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = make_settings(self.tmp.name)
        self.reg = {"papers": [{"id": PID, "category": "测试",
                                "title": "A Test Paper"}]}
        self.HTML = wrap(f"<h2>Abstract</h2><p>{PARA}</p>"
                         "<table><tr><td>1.5</td><td>2.5</td></tr></table>")

    def tearDown(self):
        self.tmp.cleanup()

    def _cache(self):
        return json.loads(
            self.settings.cache_file(PID).read_text(encoding="utf-8"))

    def _run(self, translate, force=False):
        with mock.patch.object(bilingual, "fetch_paper_html",
                               return_value=(self.HTML, "test",
                                             "https://example.test/html/")), \
             mock.patch("time.sleep"):
            return build_bilingual(PID, self.reg, self.settings,
                                   translator=translate, force=force)

    def test_failed_translation_is_not_persisted(self):
        out = self._run(failing_translator())
        cache = self._cache()
        self.assertNotIn(PARA, cache)
        self.assertFalse([v for v in cache.values()
                          if isinstance(v, str)
                          and v.startswith(self.settings.fail_mark)])
        # 本次输出里仍要有可见的失败提示
        self.assertIn(self.settings.fail_mark,
                      out.read_text(encoding="utf-8"))

    def test_stale_failure_cache_is_pruned_and_retried(self):
        self.settings.cache_file(PID).write_text(
            json.dumps({PARA: f"{self.settings.fail_mark} 翻译失败: 旧记录"}),
            encoding="utf-8")
        out = self._run(echo_translator("【译文】"))
        self.assertEqual(self._cache()[PARA], "【译文】")
        self.assertNotIn(self.settings.fail_mark,
                         out.read_text(encoding="utf-8"))

    def test_successful_translation_is_cached(self):
        self._run(echo_translator("【译文】"))
        self.assertEqual(self._cache()[PARA], "【译文】")

    def test_nothing_retranslated_when_cache_is_warm(self):
        """这里必须 force。

        第二次调用若不 force,会被 build_bilingual 的「已生成」判断提前
        拦掉——second.calls == [] 照样成立,但验证的已经不是缓存语义了。
        绿灯掩盖覆盖失效,比红灯更危险。
        """
        self._run(echo_translator("【译文】"))
        second = echo_translator("【译文】")
        self._run(second, force=True)
        self.assertEqual(second.calls, [])

    def test_cache_is_flushed_incrementally(self):
        """中途中断不该丢掉已翻好的部分——每 20 段要落盘一次。"""
        flush_every = self.settings.cache_flush_every
        n = flush_every + 5
        html = wrap("".join(f"<p>{PARA} index {i} trailing filler</p>"
                            for i in range(n)))
        calls = {"n": 0}

        def flaky(text):
            calls["n"] += 1
            if calls["n"] > flush_every:
                raise KeyboardInterrupt          # 模拟 Ctrl-C
            return "【译文】"

        with mock.patch.object(bilingual, "fetch_paper_html",
                               return_value=(html, "test", "https://x/")), \
             mock.patch("time.sleep"), self.assertRaises(KeyboardInterrupt):
            build_bilingual(PID, self.reg, self.settings,
                            translator=FakeTranslator(flaky))

        self.assertEqual(len(self._cache()), flush_every)

    def test_title_is_cached_under_its_own_key(self):
        self._run(echo_translator("【译文】"))
        self.assertIn("TITLE::A Test Paper", self._cache())


class TestBilingualSkip(unittest.TestCase):
    """重跑 `--bilingual all` 不该把已生成的论文重新抓一遍。

    抓 HTML 排在「哪些段落需要翻译」的判断之前,所以跳过必须发生在入口处,
    否则即使译文全部命中缓存,每篇仍要发一次网络请求。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = make_settings(self.tmp.name)
        self.reg = {"papers": [{"id": PID, "category": "测试",
                                "title": "A Test Paper"}]}
        self.HTML = wrap(f"<h2>Abstract</h2><p>{PARA}</p>")

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, force=False, translator=None):
        """返回 (输出路径, fetch_paper_html 的 mock)。"""
        with mock.patch.object(bilingual, "fetch_paper_html",
                               return_value=(self.HTML, "test",
                                             "https://x/")) as fetch, \
             mock.patch("time.sleep"):
            out = build_bilingual(PID, self.reg, self.settings,
                                  translator=translator or echo_translator(),
                                  force=force)
        return out, fetch

    def _mark_generated(self, content="# 手工内容"):
        """绕过生成流程,直接造出「登记表有字段 + 文件在磁盘上」的状态。"""
        out = self.settings.bilingual_dir / "测试" / f"{PID} 中英对照.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        self.reg["papers"][0]["bilingual"] = str(
            out.relative_to(self.settings.base_dir))
        return out

    def test_second_run_skips_without_fetching_html(self):
        first, _ = self._run()
        self.assertTrue(first.exists())
        out, fetch = self._run()
        self.assertEqual(out, first)
        self.assertFalse(fetch.called, "已生成的论文不该再抓一次 HTML")

    def test_skip_leaves_existing_file_untouched(self):
        out = self._mark_generated()
        result, fetch = self._run()
        self.assertEqual(result, out)
        self.assertFalse(fetch.called)
        self.assertEqual(out.read_text(encoding="utf-8"), "# 手工内容")

    def test_force_rebuilds(self):
        out = self._mark_generated()
        result, fetch = self._run(force=True)
        self.assertTrue(fetch.called)
        self.assertEqual(result, out)
        self.assertNotEqual(out.read_text(encoding="utf-8"), "# 手工内容")

    def test_deleted_output_is_regenerated_without_force(self):
        """手工删掉 md 之后要能重建——只看登记表字段会漏掉这种情况。"""
        out = self._mark_generated()
        out.unlink()
        result, fetch = self._run()
        self.assertTrue(fetch.called)
        self.assertTrue(result.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
