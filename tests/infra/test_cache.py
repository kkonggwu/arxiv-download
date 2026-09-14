"""翻译缓存:失败不落盘 + 增量落盘 + 清理历史疤痕。"""

import json
import tempfile
import unittest
from pathlib import Path

from paperkit.infra.cache import TranslationCache
from tests.helpers import bootstrap  # noqa: F401

FAIL = "⚠"


class TestTranslationCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "1234.56789.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _raw(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_missing_file_starts_empty(self):
        cache = TranslationCache(self.path).load()
        self.assertEqual(len(cache), 0)

    def test_round_trip(self):
        cache = TranslationCache(self.path, flush_every=0).load()
        cache.put("hello", "你好")
        cache.flush()
        self.assertEqual(self._raw(), {"hello": "你好"})
        self.assertEqual(TranslationCache(self.path).load()["hello"], "你好")

    def test_stale_failure_entries_are_pruned_on_load(self):
        self.path.write_text(
            json.dumps({"a": f"{FAIL} 翻译失败: 旧记录", "b": "正常"}),
            encoding="utf-8")
        cache = TranslationCache(self.path).load()
        self.assertEqual(cache.pruned, 1)
        self.assertNotIn("a", cache)      # 删掉即视为未命中,本次会重试
        self.assertIn("b", cache)

    def test_incremental_flush_writes_every_n_puts(self):
        cache = TranslationCache(self.path, flush_every=3).load()
        for i in range(3):
            cache.put(f"k{i}", f"v{i}")
        # 第 3 条触发落盘,不等到全部翻完
        self.assertEqual(len(self._raw()), 3)
        cache.put("k3", "v3")
        self.assertEqual(len(self._raw()), 3)   # 还没到下一个阈值
        cache.flush()
        self.assertEqual(len(self._raw()), 4)

    def test_flush_is_atomic_no_temp_left(self):
        cache = TranslationCache(self.path, flush_every=0).load()
        cache.put("a", "b")
        cache.flush()
        self.assertFalse(self.path.with_name(self.path.name + ".tmp").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
