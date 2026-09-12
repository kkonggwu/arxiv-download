"""CLI:参数解析、退出码、三种模式的分发。

run() 的 argv / env / base_dir 都可注入,所以可以完整驱动一遍而不碰真实
环境、不联网。
"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from tests.helpers import bootstrap  # noqa: F401
from paperkit.cli import build_parser, run
from paperkit.cli.main import _summary
from paperkit.infra.storage import RegistryStore


def capture(fn, *args, **kwargs) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = fn(*args, **kwargs)
    return code, buf.getvalue()


class TestParser(unittest.TestCase):
    def test_help_is_available(self):
        # 早期版本 add_help=False 又没别的参数占用 -h,导致 --help 报
        # "unrecognized arguments",帮助只能靠不带参数触发
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit) as ctx:
            build_parser().parse_args(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("--bilingual", buf.getvalue())

    def test_defaults(self):
        args = build_parser().parse_args([])
        self.assertEqual(args.papers, [])
        self.assertFalse(args.all)
        self.assertIsNone(args.translator)

    def test_bilingual_takes_id_or_all(self):
        self.assertEqual(
            build_parser().parse_args(["-b", "all"]).bilingual, "all")


class TestExitCodes(unittest.TestCase):
    def test_all_success(self):
        self.assertEqual(_summary(0, 10), 0)

    def test_partial_failure(self):
        self.assertEqual(_summary(3, 10), 2)

    def test_total_failure(self):
        self.assertEqual(_summary(10, 10), 1)


class TestListMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = RegistryStore(self.root / "papers.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_registry(self):
        self.store.save({"papers": []})
        code, out = capture(run, ["--list"], env={}, base_dir=self.root)
        self.assertEqual(code, 0)
        self.assertIn("共 0 篇", out)

    def test_shows_pending_metadata_entries(self):
        self.store.save({"papers": [{"id": "1706.03762", "category": "经典"}]})
        _, out = capture(run, ["--list"], env={}, base_dir=self.root)
        self.assertIn("待补全元数据", out)

    def test_tick_marks_pdf_present_on_disk(self):
        self.store.save({"papers": [
            {"id": "1706.03762", "category": "经典", "file": "a.pdf"}]})
        _, out = capture(run, ["--list"], env={}, base_dir=self.root)
        self.assertIn("[  ]", out)          # 文件不在磁盘上,不该打勾

        (self.root / "papers" / "经典").mkdir(parents=True)
        (self.root / "papers" / "经典" / "a.pdf").write_bytes(b"%PDF")
        _, out = capture(run, ["--list"], env={}, base_dir=self.root)
        self.assertIn("[✓ ]", out)

    def test_diamond_checks_disk_not_just_registry(self):
        md = self.root / "papers" / "双语" / "x.md"
        self.store.save({"papers": [
            {"id": "1", "category": "c", "file": "a.pdf",
             "bilingual": "papers/双语/x.md"}]})
        _, out = capture(run, ["--list"], env={}, base_dir=self.root)
        self.assertNotIn("[ ◈]", out)       # 登记表里有,但文件不存在

        md.parent.mkdir(parents=True)
        md.write_text("# x", encoding="utf-8")
        _, out = capture(run, ["--list"], env={}, base_dir=self.root)
        self.assertIn("[ ◈]", out)


class TestBilingualMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        RegistryStore(self.root / "papers.json").save(
            {"papers": [{"id": "1706.03762", "category": "经典"}]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_success_returns_zero(self):
        with mock.patch("paperkit.cli.main.build_bilingual") as g, \
             mock.patch("time.sleep"):
            code, _ = capture(run, ["-b", "1706.03762"], env={},
                              base_dir=self.root)
        self.assertEqual(code, 0)
        self.assertTrue(g.called)

    def test_single_failure_does_not_abort_the_batch(self):
        from paperkit.errors import SourceUnavailable
        with mock.patch("paperkit.cli.main.build_bilingual",
                        side_effect=SourceUnavailable("no html")), \
             mock.patch("time.sleep"):
            code, out = capture(run, ["-b", "1706.03762"], env={},
                                base_dir=self.root)
        self.assertEqual(code, 1)           # 唯一一篇失败了
        self.assertIn("失败", out)

    def test_parser_failure_is_reported_not_raised(self):
        from paperkit.errors import SourceUnavailable
        with mock.patch("paperkit.cli.main.build_bilingual",
                        side_effect=SourceUnavailable("x")), \
             mock.patch("time.sleep"):
            code, _ = capture(run, ["-b", "1706.03762"], env={},
                              base_dir=self.root)
        self.assertIsInstance(code, int)


class TestSettingsFromCli(unittest.TestCase):
    def test_translator_flag_reaches_settings(self):
        with mock.patch("paperkit.cli.main.build_bilingual") as g, \
             mock.patch("time.sleep"), \
             tempfile.TemporaryDirectory() as tmp:
            RegistryStore(Path(tmp) / "papers.json").save(
                {"papers": [{"id": "1", "category": "c"}]})
            run(["-b", "1", "-t", "openai", "-p", "http://p:1"],
                env={}, base_dir=tmp)
        settings = g.call_args.args[2]
        self.assertEqual(settings.translate_backend, "openai")
        self.assertEqual(settings.proxy, "http://p:1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
