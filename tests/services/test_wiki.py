"""services/wiki.py:is_in_wiki 与 link_wiki 的单元测试。"""

import tempfile
import unittest
from pathlib import Path

from paperkit.config import Settings
from paperkit.errors import ConfigError
from paperkit.infra.storage import RegistryStore
from paperkit.services import is_in_wiki, link_wiki, load_registry
from tests.helpers import bootstrap  # noqa: F401


class TestIsInWiki(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(base_dir=Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_false_when_no_field(self):
        self.assertFalse(is_in_wiki({"id": "1"}, self.settings))

    def test_false_when_field_points_at_missing_file(self):
        self.assertFalse(is_in_wiki(
            {"id": "1", "wiki": "wiki/sources/x.md"}, self.settings))

    def test_true_when_field_and_file_exist(self):
        page = self.settings.base_dir / "wiki" / "sources" / "x.md"
        page.parent.mkdir(parents=True)
        page.write_text("# x", encoding="utf-8")
        self.assertTrue(is_in_wiki(
            {"id": "1", "wiki": "wiki/sources/x.md"}, self.settings))


class TestLinkWiki(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(base_dir=Path(self.tmp.name))
        RegistryStore(self.settings.registry_path).save(
            {"papers": [{"id": "1706.03762", "category": "经典"}]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_sets_field_and_persists(self):
        reg = load_registry(self.settings)
        link_wiki("1706.03762", "wiki/sources/x.md", reg, self.settings)
        saved = RegistryStore(self.settings.registry_path).load()
        self.assertEqual(saved["papers"][0]["wiki"], "wiki/sources/x.md")

    def test_normalizes_id_from_abs_link(self):
        reg = load_registry(self.settings)
        link_wiki("https://arxiv.org/abs/1706.03762", "wiki/sources/x.md",
                  reg, self.settings)
        saved = RegistryStore(self.settings.registry_path).load()
        self.assertEqual(saved["papers"][0]["wiki"], "wiki/sources/x.md")

    def test_unknown_id_raises(self):
        reg = load_registry(self.settings)
        with self.assertRaises(ConfigError):
            link_wiki("9999.99999", "wiki/sources/x.md", reg, self.settings)


if __name__ == "__main__":
    unittest.main(verbosity=2)
