"""翻译后端的选择与调度。

后端注册表 + build_translator() 是唯一的「选哪个后端」的地方。新增一个后端
只需要:写一个满足 Translator 协议的类 -> 在 _BUILDERS 里加一行。
重构前这一步要改 5 处并新增一个模块级全局。
"""

from collections.abc import Callable

from ...config import Settings
from ...errors import TranslateError
from .base import Translator, retrying_translate, split_for_translate  # noqa: F401
from .google import GoogleTranslator
from .openai import OpenAITranslator

_BUILDERS: dict[str, Callable[[Settings], Translator]] = {
    "google": lambda s: GoogleTranslator(s.google_translate_url, proxy=s.proxy),
    "openai": lambda s: OpenAITranslator(
        s.openai_base_url, s.openai_model, s.translate_api_key,
        proxy=s.proxy, chunk_limit=s.openai_chunk_limit),
}


def available_backends() -> list[str]:
    return sorted(_BUILDERS)


def build_translator(settings: Settings) -> Translator:
    """按 settings.translate_backend 造一个翻译器。"""
    builder = _BUILDERS.get(settings.translate_backend)
    if builder is None:
        raise TranslateError(
            f"未知翻译后端: {settings.translate_backend}"
            f"(可选 {'/'.join(available_backends())})")
    return builder(settings)


def translate_one(text: str, settings: Settings,
                  translator: Translator | None = None) -> str:
    """翻译一段英文。translator 传了就复用它,否则按配置新建。"""
    backend = translator or build_translator(settings)
    return retrying_translate(backend, text, retries=settings.translate_retries)


__all__ = ["Translator", "GoogleTranslator", "OpenAITranslator",
           "build_translator", "translate_one", "available_backends",
           "retrying_translate", "split_for_translate"]
