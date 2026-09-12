"""基础设施层:网络、文件、日志、缓存、翻译后端等一切副作用都集中在这里。

依赖方向约束(由 tests/test_layering.py 在 CI 层强制):
    infra 可以依赖 domain / config / errors
    infra **不得**依赖 services / cli
"""

from . import (arxiv_api, cache, http, logging,  # noqa: F401
               storage, translate)

__all__ = ["arxiv_api", "cache", "http", "logging", "storage", "translate"]
