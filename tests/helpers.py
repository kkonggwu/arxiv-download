"""测试共享工具:假翻译器、HTML 包装、路径准备。

重构后不再用 mock.patch 去改模块级全局,而是把依赖注入进去:
  * 翻译用 FakeTranslator(满足 Translator 协议)
  * 产物路径用 Settings(base_dir=临时目录)
因此测试之间没有隐式共享状态,可以任意顺序、并行执行。
"""

import sys
from pathlib import Path

# 让 paperkit 可导入(从任意工作目录运行测试都没问题)
PROJECT_ROOT = next(p for p in Path(__file__).resolve().parents
                    if (p / "paperkit").is_dir())
sys.path[:0] = [str(PROJECT_ROOT)]

# 各测试文件 `from tests.helpers import bootstrap` 即可触发上面的引导
bootstrap = True

from paperkit.config import Settings  # noqa: E402
from paperkit.infra.storage import RegistryStore  # noqa: E402

PARA = "This is a sufficiently long paragraph of English text for parsing."  # >40 字符


class FakeTranslator:
    """满足 Translator 协议的假翻译器:零网络、可断言调用次数。"""

    name = "fake"

    def __init__(self, fn):
        self.fn = fn
        self.calls: list[str] = []

    def translate(self, text: str) -> str:
        self.calls.append(text)
        return self.fn(text)


def echo_translator(replacement: str = "【译文】") -> FakeTranslator:
    return FakeTranslator(lambda text: replacement)


def failing_translator(exc: Exception | None = None) -> FakeTranslator:
    def boom(text):
        raise exc or RuntimeError("boom")
    return FakeTranslator(boom)


def wrap(body: str) -> str:
    """包一层论文正文容器,模拟 arXiv/ar5iv 的页面结构。"""
    return (f'<div class="ltx_page_main">{body}</div>'
            f'<div class="ltx_page_footer">x</div>')


def make_settings(root: Path, **overrides) -> Settings:
    """在临时目录里建一套配置,并把登记表初始化成空骨架。"""
    settings = Settings(base_dir=Path(root), **overrides)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    RegistryStore(settings.registry_path).save({"papers": []})
    return settings
