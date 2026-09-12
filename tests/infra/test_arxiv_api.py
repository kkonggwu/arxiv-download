"""arXiv 元数据与 HTML 抓取。

打桩打在**使用它的模块**上(paperkit.infra.arxiv_api),因为 arxiv_api 用
`from .http import http_get` 绑定了名字,查找发生在它自己的命名空间里。
"""

import unittest
from unittest import mock

from tests.helpers import bootstrap  # noqa: F401
from paperkit.errors import SourceUnavailable
from paperkit.infra import arxiv_api

ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Attention Is All You Need</title>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <published>2017-06-12T17:57:34Z</published>
  </entry>
</feed>"""


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
                               side_effect=OSError("down")):
            with self.assertRaises(SourceUnavailable):
                arxiv_api.fetch_paper_html("1706.03762")

    def test_page_without_body_falls_through(self):
        with mock.patch.object(arxiv_api, "http_get",
                               return_value=b"<html>nothing here</html>"):
            with self.assertRaises(SourceUnavailable):
                arxiv_api.fetch_paper_html("1706.03762")


if __name__ == "__main__":
    unittest.main(verbosity=2)
