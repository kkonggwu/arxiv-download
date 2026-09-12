"""文件名与目录名生成(Windows 合法字符、长度上限)。"""

import unittest

from tests.helpers import bootstrap  # noqa: F401  (触发 sys.path 引导)
from paperkit.domain import make_filename, sanitize


class TestSanitize(unittest.TestCase):
    def test_illegal_characters_are_stripped(self):
        self.assertEqual(sanitize('a<b>c:d"e/f\\g|h?i*j'), "abcdefghij")

    def test_whitespace_is_collapsed_and_edges_trimmed(self):
        self.assertEqual(sanitize("  a   b  "), "a b")
        self.assertEqual(sanitize("name."), "name")

    def test_fullwidth_is_normalized(self):
        # NFKC:全角字母 -> 半角
        self.assertEqual(sanitize("ＡＢＣ"), "ABC")

    def test_length_is_capped(self):
        self.assertEqual(len(sanitize("x" * 500)), 200)


class TestMakeFilename(unittest.TestCase):
    def test_filename_shape(self):
        meta = {"year": "2017", "title": "Attention Is All You Need",
                "authors": ["Ashish Vaswani", "Noam Shazeer"],
                "id": "1706.03762"}
        self.assertEqual(
            make_filename(meta),
            "2017 - Vaswani et al. - Attention Is All You Need "
            "[1706.03762].pdf")

    def test_single_author_has_no_et_al(self):
        meta = {"year": "2025", "title": "Solo", "authors": ["Jane Doe"],
                "id": "2501.00001"}
        self.assertEqual(make_filename(meta),
                         "2025 - Doe - Solo [2501.00001].pdf")

    def test_missing_authors_falls_back_to_unknown(self):
        meta = {"year": "2025", "title": "T", "id": "2501.00001"}
        self.assertIn("Unknown", make_filename(meta))

    def test_pdf_suffix_survives_a_very_long_title(self):
        # 早期 bug:先截断再拼 .pdf,超长标题会把后缀截掉
        meta = {"year": "2025", "title": "T" * 500, "authors": [],
                "id": "2501.00001"}
        self.assertTrue(make_filename(meta).endswith(".pdf"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
