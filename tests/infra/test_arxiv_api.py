"""arXiv 元数据与 HTML 抓取。

打桩打在**使用它的模块**上(paperkit.infra.arxiv_api),因为 arxiv_api 用
`from .http import http_get` 绑定了名字,查找发生在它自己的命名空间里。
"""

import io
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest import mock

from paperkit.errors import SourceUnavailable
from paperkit.infra import arxiv_api
from tests.helpers import bootstrap  # noqa: F401

ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Attention Is All You Need</title>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <published>2017-06-12T17:57:34Z</published>
  </entry>
</feed>"""

# 结构照抄真实 abs 页面(2201.11903,2026-09 实测),包含 <span class="descriptor">
# 前缀与 href 里的 &amp; 实体——这两处正是解析最容易出错的地方
ABS_PAGE = """<html><body>
    <div class="dateline">
  [Submitted on 28 Jan 2022 (<a href="https://arxiv.org/abs/2201.11903v1">v1</a>), last revised 10 Jan 2023 (this version, v6)]</div>
    <h1 class="title mathjax"><span class="descriptor">Title:</span>Chain-of-Thought Prompting Elicits Reasoning in Large Language Models</h1>
    <div class="authors"><span class="descriptor">Authors:</span><a href="https://arxiv.org/search/cs?searchtype=author&amp;query=Wei,+J" rel="nofollow">Jason Wei</a>, <a href="https://arxiv.org/search/cs?searchtype=author&amp;query=Wang,+X" rel="nofollow">Xuezhi Wang</a>, <a href="https://arxiv.org/search/cs?searchtype=author&amp;query=Zhou,+D" rel="nofollow">Denny Zhou</a></div>
</body></html>"""


class TestFetchMetadata(unittest.TestCase):
    def test_success_parses_fields(self):
        with mock.patch.object(arxiv_api, "http_get",
                               return_value=ATOM_XML.encode()):
            meta = arxiv_api.fetch_metadata("1706.03762")
        self.assertEqual(meta["title"], "Attention Is All You Need")
        self.assertEqual(meta["year"], "2017")
        self.assertEqual(meta["authors"], ["Ashish Vaswani", "Noam Shazeer"])

    def test_network_failure_returns_none(self):
        with mock.patch.object(arxiv_api, "http_get",
                               side_effect=OSError("unreachable")):
            self.assertIsNone(arxiv_api.fetch_metadata("1706.03762"))

    def test_empty_title_returns_none(self):
        xml = ATOM_XML.replace("Attention Is All You Need", "")
        with mock.patch.object(arxiv_api, "http_get", return_value=xml.encode()):
            self.assertIsNone(arxiv_api.fetch_metadata("1706.03762"))

    def test_missing_entry_returns_none(self):
        with mock.patch.object(arxiv_api, "http_get",
                               return_value=b"<feed></feed>"):
            self.assertIsNone(arxiv_api.fetch_metadata("1706.03762"))

    def test_duplicate_authors_are_deduped_in_order(self):
        # arXiv API 实测会重复返回同一个作者(2501.12948 返回 200 个名字,
        # 其中两个各出现两次),按首次出现顺序去重
        xml = ATOM_XML.replace(
            "<author><name>Noam Shazeer</name></author>",
            "<author><name>Noam Shazeer</name></author>"
            "<author><name>Ashish Vaswani</name></author>"
            "<author><name>Noam Shazeer</name></author>")
        with mock.patch.object(arxiv_api, "http_get", return_value=xml.encode()):
            meta = arxiv_api.fetch_metadata("1706.03762")
        self.assertEqual(meta["authors"], ["Ashish Vaswani", "Noam Shazeer"])

    def test_proxy_is_passed_through(self):
        from paperkit.config import Settings
        settings = Settings(proxy="http://127.0.0.1:7897")
        with mock.patch.object(arxiv_api, "http_get",
                               return_value=ATOM_XML.encode()) as g:
            arxiv_api.fetch_metadata("1706.03762", settings)
        self.assertEqual(g.call_args.kwargs.get("proxy"), "http://127.0.0.1:7897")

    def test_rate_limit_is_reported_distinctly(self):
        """429 是可重试的限流,日志不能和「论文不存在」混为一谈。

        两者都返回 None,但用户该做的事完全不同:限流等几分钟再来,
        不存在等多久都没用。实测 export.arxiv.org 会持续返回 429。
        """
        err = urllib.error.HTTPError("http://x", 429, "Too Many Requests",
                                     {}, None)
        buf = io.StringIO()
        with mock.patch.object(arxiv_api, "http_get", side_effect=err), \
             redirect_stdout(buf):
            self.assertIsNone(arxiv_api.fetch_metadata("2201.11903"))
        out = buf.getvalue()
        self.assertIn("429", out)
        self.assertIn("限流", out)

    def test_other_errors_keep_the_generic_message(self):
        buf = io.StringIO()
        with mock.patch.object(arxiv_api, "http_get",
                               side_effect=OSError("unreachable")), \
             redirect_stdout(buf):
            self.assertIsNone(arxiv_api.fetch_metadata("1706.03762"))
        self.assertIn("元数据获取失败", buf.getvalue())
        self.assertNotIn("限流", buf.getvalue())


class TestAbsPageFallback(unittest.TestCase):
    """export.arxiv.org 长期 429 时的兜底路径。

    429 是 arXiv 侧的限流,换代理也换不掉,所以兜底不是「优化」而是必需:
    没有它,接口一限流所有论文都只能登记成 id,标题永远是缺的。
    """

    def _api_down_abs_ok(self, url, **kwargs):
        if "export.arxiv.org" in url:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
        return ABS_PAGE.encode()

    def test_abs_page_parses_title_authors_and_year(self):
        with mock.patch.object(arxiv_api, "http_get", return_value=ABS_PAGE.encode()):
            meta = arxiv_api._metadata_from_abs_page("2201.11903", None)
        self.assertEqual(
            meta["title"],
            "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models")
        self.assertEqual(meta["authors"], ["Jason Wei", "Xuezhi Wang", "Denny Zhou"])
        self.assertEqual(meta["year"], "2022")

    def test_descriptor_prefix_is_not_left_in_the_title(self):
        # <span class="descriptor">Title:</span> 只剥标签会留下「Title:」,
        # 那会原样进文件名
        with mock.patch.object(arxiv_api, "http_get", return_value=ABS_PAGE.encode()):
            meta = arxiv_api._metadata_from_abs_page("2201.11903", None)
        self.assertFalse(meta["title"].startswith("Title"))
        self.assertNotIn("Authors:", " ".join(meta["authors"]))

    def test_rate_limited_api_falls_back_to_abs_page(self):
        buf = io.StringIO()
        with mock.patch.object(arxiv_api, "http_get",
                               side_effect=self._api_down_abs_ok), redirect_stdout(buf):
            meta = arxiv_api.fetch_metadata("2201.11903")
        self.assertTrue(meta["title"].startswith("Chain-of-Thought"))
        self.assertEqual(meta["year"], "2022")
        # 兜底成功就不该再吓唬用户说限流
        self.assertIn("abs 页面", buf.getvalue())
        self.assertNotIn("429", buf.getvalue())

    def test_fallback_metadata_produces_a_real_filename(self):
        # 兜底的**唯一目的**是让文件名可用,所以直接断言最终产物
        from paperkit.domain.naming import make_filename
        with mock.patch.object(arxiv_api, "http_get",
                               side_effect=self._api_down_abs_ok):
            meta = arxiv_api.fetch_metadata("2201.11903")
        name = make_filename(meta)
        self.assertTrue(name.startswith("2022 - Wei et al. - Chain-of-Thought"))
        self.assertTrue(name.endswith("[2201.11903].pdf"))

    def test_no_second_request_when_api_succeeds(self):
        # 成功路径不能白白多打一次网络
        with mock.patch.object(arxiv_api, "http_get",
                               return_value=ATOM_XML.encode()) as g:
            arxiv_api.fetch_metadata("1706.03762")
        self.assertEqual(g.call_count, 1)

    def test_both_paths_down_still_reports_rate_limit(self):
        # 兜底也失败时,原来的 429 提示必须原样保留,不能静默
        err = urllib.error.HTTPError("http://x", 429, "Too Many Requests", {}, None)
        buf = io.StringIO()
        with mock.patch.object(arxiv_api, "http_get", side_effect=err) as g, \
             redirect_stdout(buf):
            meta = arxiv_api.fetch_metadata("2201.11903")
        self.assertIsNone(meta)
        self.assertEqual(g.call_count, 2)   # API 一次 + abs 页一次
        self.assertIn("429", buf.getvalue())
        self.assertIn("限流", buf.getvalue())

    def test_abs_page_without_title_is_not_half_parsed(self):
        # 宁可返回 None(退化成待补全),也不能返回缺标题的半成品
        with mock.patch.object(arxiv_api, "http_get",
                               return_value=b"<html><body>404</body></html>"):
            self.assertIsNone(arxiv_api._metadata_from_abs_page("2201.11903", None))


class TestFetchPaperHtml(unittest.TestCase):
    PAGE = "<html><div class='ltx_page_main'><p>hi</p></div></html>"

    def test_arxiv_source_preferred(self):
        with mock.patch.object(arxiv_api, "http_get",
                               return_value=self.PAGE.encode()) as g:
            html, source, base = arxiv_api.fetch_paper_html("2501.12948")
        self.assertEqual(source, "arxiv")
        self.assertEqual(base, "https://arxiv.org/html/")
        self.assertEqual(g.call_count, 1)

    def test_falls_back_to_ar5iv_with_its_own_base(self):
        def only_ar5iv(url, **kwargs):
            if "ar5iv" in url:
                return self.PAGE.encode()
            raise OSError("blocked")

        with mock.patch.object(arxiv_api, "http_get", side_effect=only_ar5iv):
            _, source, base = arxiv_api.fetch_paper_html("1706.03762")
        self.assertEqual(source, "ar5iv")
        # 基址必须跟着来源走,写死 arxiv.org 会让图片全 404
        self.assertEqual(base, "https://ar5iv.labs.arxiv.org")

    def test_both_sources_down_raises_source_unavailable(self):
        # 不可重试的语义:纯扫描版 PDF 重跑一万次也一样
        with mock.patch.object(arxiv_api, "http_get",
                               side_effect=OSError("down")), self.assertRaises(SourceUnavailable):
            arxiv_api.fetch_paper_html("1706.03762")

    def test_page_without_body_falls_through(self):
        with mock.patch.object(arxiv_api, "http_get",
                               return_value=b"<html>nothing here</html>"), \
             self.assertRaises(SourceUnavailable):
            arxiv_api.fetch_paper_html("1706.03762")


if __name__ == "__main__":
    unittest.main(verbosity=2)
