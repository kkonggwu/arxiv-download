"""插图本地化:落到 assets/ 并改成相对路径,离线也能看图。"""

import tempfile
import unittest
from unittest import mock

from paperkit.services import images
from paperkit.services.images import asset_relpath, localize_images
from tests.helpers import bootstrap, make_settings  # noqa: F401

PID = "1234.56789"
BASE = "https://arxiv.org/html/"


class TestAssetRelpath(unittest.TestCase):
    def test_arxiv_style_path(self):
        rel = asset_relpath(f"{BASE}{PID}v2/plot.svg")
        self.assertEqual(rel.as_posix(), f"{PID}v2/plot.svg")

    def test_ar5iv_html_prefix_is_stripped(self):
        rel = asset_relpath("https://ar5iv.labs.arxiv.org/html/1706.03762/"
                            "assets/x.svg")
        self.assertEqual(rel.as_posix(), "1706.03762/assets/x.svg")

    def test_path_traversal_is_neutralised(self):
        rel = asset_relpath(f"{BASE}../../etc/passwd")
        self.assertNotIn("..", rel.as_posix())


class TestLocalizeImages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = make_settings(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _lines(self):
        return [f"![Refer to caption]({PID}v2/plot.svg)", ""]

    def _dest(self):
        return (self.settings.assets_dir(PID) / f"{PID}v2" / "plot.svg")

    def test_relative_url_is_downloaded_and_rewritten(self):
        with mock.patch.object(images, "http_get",
                               return_value=b"<svg/>") as g:
            out = localize_images(self._lines(), PID, BASE, self.settings)
        self.assertEqual(
            out[0],
            f"![Refer to caption](../assets/{PID}/{PID}v2/plot.svg)")
        self.assertEqual(self._dest().read_bytes(), b"<svg/>")
        g.assert_called_once_with(f"https://arxiv.org/html/{PID}v2/plot.svg",
                                  timeout=60, proxy=None)

    def test_existing_file_is_reused_without_request(self):
        dest = self._dest()
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"<svg/>")
        with mock.patch.object(images, "http_get") as g:
            out = localize_images(self._lines(), PID, BASE, self.settings)
        self.assertFalse(g.called)
        self.assertIn(f"../assets/{PID}/{PID}v2/plot.svg", out[0])

    def test_failure_falls_back_to_absolute_url(self):
        with mock.patch.object(images, "http_get",
                               side_effect=OSError("boom")):
            out = localize_images(self._lines(), PID, BASE, self.settings)
        self.assertIn(f"https://arxiv.org/html/{PID}v2/plot.svg", out[0])

    def test_html_response_is_rejected(self):
        with mock.patch.object(images, "http_get",
                               return_value=b"<!DOCTYPE html><html>"):
            out = localize_images(self._lines(), PID, BASE, self.settings)
        self.assertIn("https://arxiv.org", out[0])

    def test_absolute_url_is_left_alone(self):
        lines = ["![x](https://example.com/a.png)"]
        with mock.patch.object(images, "http_get") as g:
            out = localize_images(lines, PID, BASE, self.settings)
        self.assertEqual(out, lines)
        self.assertFalse(g.called)

    def test_fenced_code_block_is_not_rewritten(self):
        """代码块里是 prompt 模板原文，出现 ![](...) 字样也不能被改写。"""
        lines = ["```",
                 f"![not an image]({PID}v2/x.svg)",
                 "```",
                 f"![real]({PID}v2/plot.svg)"]
        with mock.patch.object(images, "http_get", return_value=b"<svg/>"):
            out = localize_images(lines, PID, BASE, self.settings)
        self.assertEqual(out[1], f"![not an image]({PID}v2/x.svg)")
        self.assertIn("../assets/", out[3])

    def test_tilde_fence_is_also_respected(self):
        lines = ["~~~", f"![x]({PID}v2/x.svg)", "~~~"]
        with mock.patch.object(images, "http_get") as g:
            out = localize_images(lines, PID, BASE, self.settings)
        self.assertFalse(g.called)
        self.assertEqual(out[1], f"![x]({PID}v2/x.svg)")

    def test_no_download_rewrites_to_absolute_url(self):
        with mock.patch.object(images, "http_get") as g:
            out = localize_images(self._lines(), PID, BASE, self.settings,
                                  download=False)
        self.assertFalse(g.called)
        self.assertEqual(
            out[0],
            f"![Refer to caption](https://arxiv.org/html/{PID}v2/plot.svg)")
        self.assertFalse((self.settings.bilingual_dir / "assets").exists())

    def test_same_url_is_only_requested_once(self):
        lines = [f"![a]({PID}v2/plot.svg)", f"![b]({PID}v2/plot.svg)"]
        with mock.patch.object(images, "http_get",
                               return_value=b"<svg/>") as g:
            localize_images(lines, PID, BASE, self.settings)
        self.assertEqual(g.call_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
