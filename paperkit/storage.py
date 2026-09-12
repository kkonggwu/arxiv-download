"""兼容层:实现已移入 paperkit.infra.storage,此模块仅保留原有导入路径。"""

from .infra.storage import RegistryStore, write_text_atomic  # noqa: F401

__all__ = ["RegistryStore", "write_text_atomic"]
