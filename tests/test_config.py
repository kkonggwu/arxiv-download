"""Settings:三层覆盖优先级与派生路径。

这里是唯一读环境变量的地方,而且 env 可注入,所以测试不必再去 patch
os.environ(重构前必须这么做)。
"""

import tempfile
import unittest
from pathlib import Path

from tests.helpers import bootstrap  # noqa: F401
from paperkit.config import PROJECT_ROOT, Settings

ENV = {
    "HTTPS_PROXY": "http://env-proxy",
    "TRANSLATE_BACKEND": "openai",
    "TRANSLATE_BASE_URL": "https://env.example/v1",
    "TRANSLATE_MODEL": "env-model",
    "TRANSLATE_API_KEY": "sk-env",
}


class TestOverridePrecedence(unittest.TestCase):
    def test_cli_values_override_environment(self):
        settings = Settings.from_values(
            proxy="http://cli-proxy", translator="google", model="cli-model",
            env=ENV)
        self.assertEqual(settings.proxy, "http://cli-proxy")
        self.assertEqual(settings.translate_backend, "google")
        self.assertEqual(settings.openai_model, "cli-model")

    def test_environment_used_when_cli_absent(self):
        settings = Settings.from_values(env=ENV)
        self.assertEqual(settings.proxy, "http://env-proxy")
        self.assertEqual(settings.translate_backend, "openai")
        self.assertEqual(settings.openai_base_url, "https://env.example/v1")
        self.assertEqual(settings.translate_api_key, "sk-env")

    def test_builtin_defaults_when_everything_absent(self):
        settings = Settings.from_values(env={})
        self.assertIsNone(settings.proxy)
        self.assertEqual(settings.translate_backend, "google")
        self.assertEqual(settings.openai_model, "gpt-4o-mini")
        self.assertEqual(settings.base_dir, PROJECT_ROOT)

    def test_lowercase_proxy_env_is_accepted(self):
        self.assertEqual(
            Settings.from_values(env={"https_proxy": "http://p:1"}).proxy,
            "http://p:1")

    def test_backend_name_is_normalised(self):
        self.assertEqual(
            Settings.from_values(env={"TRANSLATE_BACKEND": " OpenAI "})
            .translate_backend, "openai")


class TestDerivedPaths(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.settings = Settings(base_dir=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_paths_hang_off_base_dir(self):
        self.assertEqual(self.settings.registry_path, self.root / "papers.json")
        self.assertEqual(self.settings.out_dir, self.root / "papers")
        self.assertEqual(self.settings.bilingual_dir, self.root / "papers" / "双语")
        self.assertEqual(self.settings.cache_dir,
                         self.root / "papers" / "双语" / ".cache")
        self.assertEqual(self.settings.assets_dir("1234.5678"),
                         self.root / "papers" / "双语" / "assets" / "1234.5678")

    def test_cache_file_is_per_backend(self):
        # 换后端要重新翻译,不能复用另一份缓存
        self.assertEqual(self.settings.cache_file("1").name, "1.json")
        openai = Settings(base_dir=self.root, translate_backend="openai")
        self.assertEqual(openai.cache_file("1").name, "1.openai.json")

    def test_settings_is_frozen(self):
        with self.assertRaises(Exception):
            self.settings.proxy = "http://changed"


if __name__ == "__main__":
    unittest.main(verbosity=2)
