"""原子写与登记表读写。

原子写是防「半截 JSON」的:缓存每 20 段落盘一次,而中断正是本项目的高频场景。
"""

import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers import bootstrap  # noqa: F401
from paperkit.infra.storage import RegistryStore, write_text_atomic


class TestWriteTextAtomic(unittest.TestCase):
    def test_replaces_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "state.json"
            target.write_text("old", encoding="utf-8")
            write_text_atomic(target, "new")
            self.assertEqual(target.read_text(encoding="utf-8"), "new")

    def test_no_temp_file_left_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "state.json"
            write_text_atomic(target, "new")
            self.assertFalse((Path(tmp) / "state.json.tmp").exists())

    def test_creates_missing_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a" / "b" / "state.json"
            write_text_atomic(target, "x")
            self.assertEqual(target.read_text(encoding="utf-8"), "x")

    def test_writes_lf_on_every_platform(self):
        """换行必须是 LF,否则和 .gitattributes 的 eol=lf 打架。

        Path.write_text 默认会把 \\n 转成 os.linesep——Windows 上写出 CRLF,
        于是每次 git 操作都警告「CRLF will be replaced by LF」。用
        read_bytes 断言,避免 read_text 的通用换行模式把差异吃掉。
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "state.json"
            write_text_atomic(target, "a\nb\n")
            self.assertEqual(target.read_bytes(), b"a\nb\n")


class TestRegistryStore(unittest.TestCase):
    def test_missing_file_yields_empty_skeleton(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RegistryStore(Path(tmp) / "papers.json")
            self.assertEqual(store.load(), {"papers": []})

    def test_round_trip_keeps_chinese_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "papers.json"
            store = RegistryStore(path)
            store.save({"papers": [{"id": "1", "category": "推理前沿"}]})
            # ensure_ascii=False:中文分类名要能直接看到,方便手改
            self.assertIn("推理前沿", path.read_text(encoding="utf-8"))
            self.assertEqual(store.load()["papers"][0]["category"], "推理前沿")

    def test_save_ends_with_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "papers.json"
            RegistryStore(path).save({"papers": []})
            self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
