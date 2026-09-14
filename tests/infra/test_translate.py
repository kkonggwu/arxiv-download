"""翻译后端:公式保护、重试语义、后端选择。"""

import json
import unittest
from unittest import mock

from paperkit.config import Settings
from paperkit.errors import TranslateError
from paperkit.infra import translate
from paperkit.infra.translate import google, openai
from paperkit.infra.translate.base import protect_formulas, retrying_translate
from tests.helpers import FakeTranslator, bootstrap, echo_translator  # noqa: F401


class TestFormulaProtection(unittest.TestCase):
    def test_inline_and_display_formulas_are_extracted(self):
        protected, formulas = protect_formulas("Let $x=1$ and $$y=2$$ hold.")
        self.assertEqual(formulas, ["$x=1$", "$$y=2$$"])
        self.assertNotIn("$x=1$", protected)
        self.assertIn("__FORMULA_0__", protected)

    def test_formulas_are_restored_after_translation(self):
        seen = {}

        def spy(text):
            seen["text"] = text
            return text                    # 占位符原样返回,应被还原成公式

        out = retrying_translate(FakeTranslator(spy), "Let $x=1$ hold.", retries=1)
        self.assertNotIn("$x=1$", seen["text"])     # 送出去时已摘掉
        self.assertIn("__FORMULA_0__", seen["text"])
        self.assertIn("$x=1$", out)                 # 回来后原样还原
        self.assertNotIn("__FORMULA_0__", out)


class TestRetrySemantics(unittest.TestCase):
    def test_success_passes_through(self):
        self.assertEqual(retrying_translate(echo_translator("你好"), "hi", 3), "你好")

    def test_empty_translation_is_treated_as_failure(self):
        with mock.patch("time.sleep"), self.assertRaises(TranslateError):
            retrying_translate(FakeTranslator(lambda t: ""), "hi", 2)

    def test_retries_then_raises_translate_error(self):
        translator = FakeTranslator(lambda t: (_ for _ in ()).throw(OSError("net")))
        with mock.patch("time.sleep") as sleeper, self.assertRaises(TranslateError):
            retrying_translate(translator, "hi", retries=3)
        self.assertEqual(len(translator.calls), 3)
        self.assertEqual(sleeper.call_count, 2)     # 最后一次失败后不再等待

    def test_keyboard_interrupt_is_not_swallowed(self):
        """Ctrl-C 必须能立刻中断,不能被当成「可重试的翻译失败」。"""
        translator = FakeTranslator(
            lambda t: (_ for _ in ()).throw(KeyboardInterrupt()))
        with self.assertRaises(KeyboardInterrupt):
            retrying_translate(translator, "hi", retries=3)


class TestBackendSelection(unittest.TestCase):
    def test_google_is_default(self):
        self.assertEqual(translate.build_translator(Settings()).name, "google")

    def test_openai_selected_by_settings(self):
        t = translate.build_translator(Settings(translate_backend="openai"))
        self.assertEqual(t.name, "openai")

    def test_unknown_backend_raises(self):
        with self.assertRaises(TranslateError):
            translate.build_translator(Settings(translate_backend="nope"))

    def test_available_backends(self):
        self.assertEqual(translate.available_backends(), ["google", "openai"])

    def test_translate_one_accepts_an_injected_translator(self):
        # 注入之后完全不走网络,也不需要 API Key
        out = translate.translate_one("hi", Settings(),
                                      translator=echo_translator("你好"))
        self.assertEqual(out, "你好")


class TestGoogleBackend(unittest.TestCase):
    def test_list_response_shape(self):
        with mock.patch.object(google, "http_get",
                               return_value=json.dumps([["你好"]]).encode()):
            out = google.GoogleTranslator("https://g/").translate("hi")
        self.assertEqual(out, "你好")

    def test_flat_string_list_shape(self):
        with mock.patch.object(google, "http_get",
                               return_value=json.dumps(["你好", "世界"]).encode()):
            out = google.GoogleTranslator("https://g/").translate("hi")
        self.assertEqual(out, "你好世界")

    def test_dict_response_shape(self):
        payload = {"sentences": [{"trans": "你好"}]}
        with mock.patch.object(google, "http_get",
                               return_value=json.dumps(payload).encode()):
            out = google.GoogleTranslator("https://g/").translate("hi")
        self.assertEqual(out, "你好")

    def test_proxy_is_forwarded(self):
        with mock.patch.object(google, "http_get",
                               return_value=json.dumps(["x"]).encode()) as g:
            google.GoogleTranslator("https://g/",
                                    proxy="http://p:1").translate("hi")
        self.assertEqual(g.call_args.kwargs.get("proxy"), "http://p:1")


class TestOpenAIBackend(unittest.TestCase):
    def test_missing_api_key_raises(self):
        t = openai.OpenAITranslator("https://api.test/v1", "m", None)
        with self.assertRaises(TranslateError):
            t.translate("hi")

    def test_successful_completion(self):
        payload = {"choices": [{"message": {"content": "你好"}}]}
        t = openai.OpenAITranslator("https://api.test/v1", "m", "sk-x")
        with mock.patch.object(openai, "http_post_json",
                               return_value=json.dumps(payload).encode()) as g:
            out = t.translate("hi")
        self.assertEqual(out, "你好")
        self.assertTrue(g.call_args.args[0].endswith("/chat/completions"))
        self.assertEqual(g.call_args.args[1]["temperature"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
