"""arXiv id 解析。两代格式都要认。"""

import sys
import unittest
from pathlib import Path

# 把项目根加入 sys.path(从任意工作目录运行都成立)
sys.path[:0] = [str(next(p for p in Path(__file__).resolve().parents
                         if (p / "paperkit").is_dir()))]

from paperkit.domain import parse_arxiv_id  # noqa: E402


class TestArxivIds(unittest.TestCase):
    def test_new_style(self):
        self.assertEqual(parse_arxiv_id("2501.12948"), "2501.12948")
        self.assertEqual(parse_arxiv_id("2501.12948v2"), "2501.12948")
        self.assertEqual(parse_arxiv_id("  2501.12948  "), "2501.12948")

    def test_links(self):
        self.assertEqual(
            parse_arxiv_id("https://arxiv.org/abs/2405.15793"), "2405.15793")
        self.assertEqual(
            parse_arxiv_id("https://arxiv.org/pdf/2405.15793v1"), "2405.15793")

    def test_old_style(self):
        # 旧版 id 是 archive/YYMMNNN,2022 年以前的老论文都用这种
        self.assertEqual(parse_arxiv_id("cs/0703045"), "cs/0703045")
        self.assertEqual(parse_arxiv_id("hep-th/9901001"), "hep-th/9901001")
        self.assertEqual(parse_arxiv_id("math.GT/0309136"), "math.GT/0309136")
        self.assertEqual(parse_arxiv_id("cond-mat/0102536"), "cond-mat/0102536")

    def test_old_style_link(self):
        self.assertEqual(
            parse_arxiv_id("https://arxiv.org/abs/cs/0703045"), "cs/0703045")

    def test_unrecognized(self):
        for bad in ("", "not-an-id", "2501", "1706.03762/extra", "cs/123"):
            self.assertIsNone(parse_arxiv_id(bad), bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
