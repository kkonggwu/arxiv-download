"""命令行层:唯一接触 argv / stdout / 环境变量的地方。

依赖方向约束(由 tests/test_layering.py 在 CI 层强制):
    cli 可以依赖 services / config / errors
    cli **不得**直接依赖 infra 或 domain 的实现细节
"""

from .main import build_parser, main, run

__all__ = ["build_parser", "main", "run"]
