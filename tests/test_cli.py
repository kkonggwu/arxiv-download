"""CLI:参数解析、退出码、三种模式的分发。

run() 的 argv / env / base_dir 都可注入,所以可以完整驱动一遍而不碰真实
环境、不联网。
"""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from paperkit.cli import build_parser, run
from paperkit.cli.main import _summary
from paperkit.infra.storage import RegistryStore
from tests.helpers import bootstrap  # noqa: F401


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
        self.assertIn("[   ]", out)         # 文件不在磁盘上,不该打勾

        (self.root / "papers" / "经典").mkdir(parents=True)
        (self.root / "papers" / "经典" / "a.pdf").write_bytes(b"%PDF")
        _, out = capture(run, ["--list"], env={}, base_dir=self.root)
        self.assertIn("[✓  ]", out)

    def test_diamond_checks_disk_not_just_registry(self):
        md = self.root / "papers" / "双语" / "x.md"
        self.store.save({"papers": [
            {"id": "1", "category": "c", "file": "a.pdf",
             "bilingual": "papers/双语/x.md"}]})
        _, out = capture(run, ["--list"], env={}, base_dir=self.root)
        self.assertNotIn("[ ◈ ]", out)      # 登记表里有,但文件不存在

        md.parent.mkdir(parents=True)
        md.write_text("# x", encoding="utf-8")
        _, out = capture(run, ["--list"], env={}, base_dir=self.root)
        self.assertIn("[ ◈ ]", out)

    def test_diamond_shows_even_when_metadata_is_missing(self):
        """元数据没补全 ≠ 没生成过对照材料——两个维度必须分开看。

        元数据接口限流时条目只有 id + category,但 --bilingual 照样能生成
        (它只要 HTML)。此前这种情况 --list 不显示 ◈,会让人以为白跑一趟。
        """
        md = self.root / "papers" / "双语" / "x.md"
        md.parent.mkdir(parents=True)
        md.write_text("# x", encoding="utf-8")
        self.store.save({"papers": [
            {"id": "2201.11903", "category": "推理前沿",
             "bilingual": "papers/双语/x.md"}]})
        _, out = capture(run, ["--list"], env={}, base_dir=self.root)
        self.assertIn("待补全元数据", out)
        self.assertIn("[ ◈ ]", out)

    def test_hexagon_checks_disk_not_just_registry(self):
        page = self.root / "wiki" / "sources" / "x.md"
        self.store.save({"papers": [
            {"id": "1", "category": "c", "file": "a.pdf",
             "wiki": "wiki/sources/x.md"}]})
        _, out = capture(run, ["--list"], env={}, base_dir=self.root)
        self.assertNotIn("[  ⬡]", out)      # 登记表里有 wiki 字段,但文件不存在

        page.parent.mkdir(parents=True)
        page.write_text("# x", encoding="utf-8")
        _, out = capture(run, ["--list"], env={}, base_dir=self.root)
        self.assertIn("[  ⬡]", out)


class TestWikiLinkMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = RegistryStore(self.root / "papers.json")
        self.store.save({"papers": [{"id": "1706.03762", "category": "经典"}]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_marks_entry_and_persists(self):
        code, out = capture(run, ["--wiki-link", "1706.03762",
                                  "wiki/sources/x.md"], env={},
                             base_dir=self.root)
        self.assertEqual(code, 0)
        self.assertEqual(self.store.load()["papers"][0]["wiki"],
                         "wiki/sources/x.md")
        self.assertIn("已标记", out)

    def test_unknown_id_returns_config_error_exit(self):
        code, out = capture(run, ["--wiki-link", "9999.99999",
                                  "wiki/sources/x.md"], env={},
                             base_dir=self.root)
        self.assertEqual(code, 3)
        self.assertIn("清单里没有", out)

    def test_warns_when_page_file_missing(self):
        code, out = capture(run, ["--wiki-link", "1706.03762",
                                  "wiki/sources/x.md"], env={},
                             base_dir=self.root)
        self.assertEqual(code, 0)
        self.assertIn("尚不存在", out)


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

    def _save(self, papers):
        RegistryStore(self.root / "papers.json").save({"papers": papers})

    def _mark_done(self, name="a.md"):
        """造出一个「登记表有字段 + 文件在磁盘上」的已生成条目。"""
        md = self.root / "papers" / "双语" / name
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text("# done", encoding="utf-8")
        return f"papers/双语/{name}"

    def test_all_skips_already_generated(self):
        rel = self._mark_done()
        self._save([
            {"id": "1111.11111", "category": "经典", "bilingual": rel},
            {"id": "2222.22222", "category": "经典"},
        ])
        with mock.patch("paperkit.cli.main.build_bilingual") as g, \
             mock.patch("time.sleep"):
            code, out = capture(run, ["-b", "all"], env={}, base_dir=self.root)
        self.assertEqual(code, 0)
        self.assertIn("跳过 1 篇已生成", out)
        self.assertEqual(g.call_count, 1)              # 只做没生成的那篇
        self.assertEqual(g.call_args.args[0], "2222.22222")

    def test_nothing_to_do_when_everything_is_done(self):
        rel = self._mark_done()
        self._save([{"id": "1111.11111", "category": "经典",
                     "bilingual": rel}])
        with mock.patch("paperkit.cli.main.build_bilingual") as g, \
             mock.patch("time.sleep"):
            code, out = capture(run, ["-b", "all"], env={}, base_dir=self.root)
        self.assertEqual(code, 0)
        self.assertIn("没有需要生成的论文", out)
        self.assertFalse(g.called)

    def test_force_ignores_generated_state(self):
        rel = self._mark_done()
        self._save([{"id": "1111.11111", "category": "经典",
                     "bilingual": rel}])
        with mock.patch("paperkit.cli.main.build_bilingual") as g, \
             mock.patch("time.sleep"):
            code, out = capture(run, ["-b", "all", "-f"], env={},
                                base_dir=self.root)
        self.assertEqual(code, 0)
        self.assertEqual(g.call_count, 1)
        self.assertNotIn("跳过", out)
        self.assertTrue(g.call_args.kwargs["force"])


class TestAddModeRepairsDegradedEntries(unittest.TestCase):
    """`papers <id>` 对已登记的「半成品」条目必须能回填元数据。

    背景:当初 export.arxiv.org 限流时只登记了 id,后来接口恢复(或走了
    abs 页兜底),再跑一次 `papers <id>` 就得把标题与文件名写进登记表。
    早期版本只在「id 不在表里」时才写入,于是 PDF 按正确名字落了盘、
    登记表却永远停在半成品状态。
    """

    FILE = "2022 - Wei et al. - Chain-of-Thought Prompting [2201.11903].pdf"
    META = {"id": "2201.11903", "title": "Chain-of-Thought Prompting",
            "authors": ["Jason Wei", "Denny Zhou"], "year": "2022"}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / "papers.json"
        RegistryStore(self.path).save(
            {"papers": [{"id": "2201.11903", "category": "推理前沿"}]})

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, entry):
        with mock.patch("paperkit.cli.main.resolve_entry", return_value=entry), \
             mock.patch("paperkit.cli.main.download_entry",
                        return_value="downloaded") as dl, \
             mock.patch("time.sleep"):
            code, out = capture(run, ["2201.11903", "-c", "推理前沿"],
                                env={}, base_dir=self.root)
        return code, out, dl

    def test_metadata_is_written_back_to_the_registry(self):
        code, _, _ = self._run({**self.META, "category": "推理前沿",
                                "file": self.FILE})
        self.assertEqual(code, 0)
        saved = RegistryStore(self.path).load()["papers"][0]
        self.assertEqual(saved["title"], "Chain-of-Thought Prompting")
        self.assertEqual(saved["authors"], ["Jason Wei", "Denny Zhou"])
        self.assertEqual(saved["file"], self.FILE)

    def test_repaired_entry_is_downloaded_with_the_real_name(self):
        _, _, dl = self._run({**self.META, "category": "推理前沿",
                              "file": self.FILE})
        self.assertEqual(dl.call_args.args[0]["file"], self.FILE)

    def test_existing_file_is_never_overwritten(self):
        # PDF 已按旧名字落盘;即便元数据解析出了新名字也不能改 file,
        # 否则登记表会指向一个不存在的文件
        RegistryStore(self.path).save({"papers": [
            {"id": "2201.11903", "category": "推理前沿", "title": "旧标题",
             "file": "old.pdf"}]})
        self._run({**self.META, "category": "推理前沿", "file": "new.pdf"})
        saved = RegistryStore(self.path).load()["papers"][0]
        self.assertEqual(saved["file"], "old.pdf")
        self.assertEqual(saved["title"], "旧标题")

    def test_metadata_still_unavailable_keeps_the_entry_degraded(self):
        code, out, dl = self._run({"id": "2201.11903", "category": "推理前沿"})
        self.assertEqual(code, 0)
        self.assertIn("元数据待补全", out)
        self.assertFalse(dl.called)          # 没有文件名就不该下载
        self.assertNotIn("file", RegistryStore(self.path).load()["papers"][0])


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
