"""运行时配置。

这里是**唯一**读取环境变量的地方。Settings 是 frozen dataclass——构造完就
不可改,由 CLI 层构造后逐层传参,不再有模块级可变全局。

重构前 proxy / 翻译后端等 5 个配置项是模块级全局,由 main() 用一条 global
语句一次性改写。后果是:同一进程内无法用两种后端翻译,单元测试必须先改
全局再跑(测试之间隐式共享状态)。现在这些都由参数显式传递。

覆盖优先级(沿用原语义):命令行 > 环境变量 > 内置默认值。
"""

import os
from dataclasses import dataclass
from pathlib import Path

# paperkit/config.py -> paperkit/ -> 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]

GOOGLE_TRANSLATE_URL = ("https://clients5.google.com/translate_a/t"
                        "?client=dict-chrome-ex&sl=en&tl=zh-CN&q=")


@dataclass(frozen=True)
class Settings:
    """一次运行的全部配置。

    base_dir 决定所有产物的落点,测试只要传 Settings(base_dir=tmp_path)
    就能完全隔离,不必再 patch 模块级路径常量。
    """

    base_dir: Path = PROJECT_ROOT
    proxy: str | None = None
    translate_backend: str = "google"
    translate_retries: int = 3          # 单段翻译的重试次数(退避 2/4/6 秒)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    translate_api_key: str | None = None
    google_translate_url: str = GOOGLE_TRANSLATE_URL
    openai_chunk_limit: int = 4000      # openai 后端一次可送更多,句子不易被切断
    cache_flush_every: int = 20         # 每翻译这么多段就把缓存落盘一次
    request_delay: float = 0.4          # 免费接口,温柔一点
    fail_mark: str = "⚠"                # 译文失败标记,带此标记的缓存条目视为未命中

    # ---- 派生产物路径(全部相对 base_dir,挪动整个文件夹也不受影响)----
    @property
    def registry_path(self) -> Path:
        return self.base_dir / "papers.json"

    @property
    def out_dir(self) -> Path:
        """PDF 与对照材料的根目录。"""
        return self.base_dir / "papers"

    @property
    def bilingual_dir(self) -> Path:
        return self.out_dir / "双语"

    @property
    def cache_dir(self) -> Path:
        return self.bilingual_dir / ".cache"

    def assets_dir(self, arxiv_id: str) -> Path:
        return self.bilingual_dir / "assets" / arxiv_id

    def cache_file(self, arxiv_id: str) -> Path:
        """翻译缓存文件。

        按后端分文件:不同后端译文质量不同,混用会让「换后端重译」失效。
        google 沿用旧的 {id}.json 命名,既有缓存可直接复用、不必重译。
        """
        if self.translate_backend == "google":
            return self.cache_dir / f"{arxiv_id}.json"
        return self.cache_dir / f"{arxiv_id}.{self.translate_backend}.json"

    @classmethod
    def from_values(cls, *, base_dir=None, proxy: str | None = None,
                    translator: str | None = None,
                    base_url: str | None = None,
                    model: str | None = None,
                    api_key: str | None = None,
                    env: dict | None = None) -> "Settings":
        """按「参数 > 环境变量 > 默认值」组装。env 可注入,便于测试。"""
        e = os.environ if env is None else env
        return cls(
            base_dir=Path(base_dir) if base_dir else PROJECT_ROOT,
            proxy=proxy or e.get("HTTPS_PROXY") or e.get("https_proxy"),
            translate_backend=(translator or e.get("TRANSLATE_BACKEND")
                               or "google").strip().lower(),
            openai_base_url=(base_url or e.get("TRANSLATE_BASE_URL")
                             or "https://api.openai.com/v1"),
            openai_model=(model or e.get("TRANSLATE_MODEL")
                          or "gpt-4o-mini"),
            translate_api_key=api_key or e.get("TRANSLATE_API_KEY"),
        )
