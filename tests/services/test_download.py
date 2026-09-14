"""下载用例:元数据失败绝不固化占位文件名。

这是本项目最贵的一个坑:一旦把占位文件名写进登记表,`--all` 的补全条件
(`"file" not in entry`)就永远为假,这篇论文会被永久钉死在错误的名字上。
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paperkit.services import download
from paperkit.services.download import download_entry, download_pdf, ensure_metadata, resolve_entry
from tests.helpers import bootstrap, make_settings  # noqa: F401

ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Attention Is All You Need</title>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <published>2017-06-12T17:57:34Z</published>
  </entry>
</feed>"""


class TestResolveEntry(unittest.TestCase):
    def test_omits_file_when_metadata_fails(self):
        with mock.patch.object(download, "fetch_metadata", return_value=None):
            entry = resolve_entry("1706.03762", "经典")
        self.assertEqual(entry, {"id": "1706.03762", "category": "经典"})
        self.assertNotIn("file", entry)

    def test_sets_file_when_metadata_ok(self):
        with mock.patch.object(download, "fetch_metadata",
                               return_value={"id": "1706.03762",
                                             "title": "Attention Is All You Need",
                                             "year": "2017",
                                             "authors": ["Ashish Vaswani"]}):
            entry = resolve_entry("1706.03762", "经典")
        self.assertIn("file", entry)
        self.assertTrue(entry["file"].endswith("[1706.03762].pdf"))

    def test_unrecognized_input_returns_none(self):
        self.assertIsNone(resolve_entry("not-an-id", "经典"))

    def test_default_category(self):
        with mock.patch.object(download, "fetch_metadata", return_value=None):
            self.assertEqual(resolve_entry("1706.03762", None)["category"],
                             "未分类")


class TestEnsureMetadata(unittest.TestCase):
    def test_leaves_entry_untouched_on_failure(self):
        entry = {"id": "1706.03762", "category": "经典"}
        with mock.patch.object(download, "fetch_metadata", return_value=None):
            self.assertFalse(ensure_metadata(entry))
        self.assertEqual(entry, {"id": "1706.03762", "category": "经典"})

    def test_is_retried_after_failure(self):
        """核心回归:第一次失败后,第二次必须还会真的去拉元数据。"""
        entry = {"id": "1706.03762", "category": "经典"}
        with mock.patch.object(download, "fetch_metadata", return_value=None):
            self.assertFalse(ensure_metadata(entry))
        self.assertNotIn("file", entry)      # 没被占位名污染

        meta = {"id": "1706.03762", "title": "Attention Is All You Need",
                "year": "2017", "authors": ["Ashish Vaswani"]}
        with mock.patch.object(download, "fetch_metadata",
                               return_value=meta) as g:
            self.assertTrue(ensure_metadata(entry))
        self.assertTrue(g.called)            # 确实重新请求了
        self.assertEqual(entry["title"], "Attention Is All You Need")
        self.assertTrue(entry["file"].endswith("[1706.03762].pdf"))


class TestDownloadPdf(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = make_settings(self.tmp.name)
        self.dest = Path(self.tmp.name) / "x.pdf"

    def tearDown(self):
        self.tmp.cleanup()

    def test_downloads_and_verifies_magic(self):
        with mock.patch.object(download, "http_get",
                               return_value=b"%PDF-1.7 data"):
            status = download_pdf("1706.03762", self.dest, self.settings)
        self.assertEqual(status, "downloaded")
        self.assertEqual(self.dest.read_bytes(), b"%PDF-1.7 data")

    def test_existing_file_is_skipped(self):
        self.dest.write_bytes(b"%PDF-1.7 old")
        with mock.patch.object(download, "http_get") as g:
            status = download_pdf("1706.03762", self.dest, self.settings)
        self.assertEqual(status, "skipped")
        self.assertFalse(g.called)

    def test_force_redownloads(self):
        self.dest.write_bytes(b"%PDF-1.7 old")
        with mock.patch.object(download, "http_get",
                               return_value=b"%PDF-1.7 new"):
            status = download_pdf("1706.03762", self.dest, self.settings,
                                  force=True)
        self.assertEqual(status, "downloaded")
        self.assertEqual(self.dest.read_bytes(), b"%PDF-1.7 new")

    def test_non_pdf_response_is_rejected(self):
        # 限流时 arXiv 会返回 HTML,不能把它存成 .pdf
        with mock.patch.object(download, "http_get",
                               return_value=b"<html>rate limited</html>"):
            status = download_pdf("1706.03762", self.dest, self.settings)
        self.assertEqual(status, "failed")
        self.assertFalse(self.dest.exists())

    def test_empty_leftover_is_cleaned_up(self):
        self.dest.write_bytes(b"")
        with mock.patch.object(download, "http_get",
                               side_effect=OSError("boom")):
            status = download_pdf("1706.03762", self.dest, self.settings,
                                  force=True)
        self.assertEqual(status, "failed")
        self.assertFalse(self.dest.exists())

    def test_proxy_is_forwarded(self):
        with mock.patch.object(download, "http_get",
                               return_value=b"%PDF-1.7") as g:
            download_pdf("1706.03762", self.dest, self.settings)
        self.assertEqual(g.call_args.kwargs.get("proxy"), None)


class TestDownloadEntry(unittest.TestCase):
    def test_lands_in_category_subdirectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(tmp)
            entry = {"id": "1706.03762", "category": "经典",
                     "file": "paper.pdf"}
            with mock.patch.object(download, "http_get",
                                   return_value=b"%PDF-1.7"):
                status = download_entry(entry, settings)
            self.assertEqual(status, "downloaded")
            self.assertTrue(
                (settings.out_dir / "经典" / "paper.pdf").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
