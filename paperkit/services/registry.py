"""登记表读写用例。

把 RegistryStore(infra) 包成面向 settings 的两个函数,这样 cli 层不必
直接 import infra——依赖矩阵里 cli 只允许依赖 services / config / errors。
"""

from ..config import Settings
from ..infra.storage import RegistryStore


def load_registry(settings: Settings | None = None) -> dict:
    """读清单;文件不存在时返回空骨架,首次使用无需手工创建。"""
    s = settings or Settings()
    return RegistryStore(s.registry_path).load()


def save_registry(reg: dict, settings: Settings | None = None) -> None:
    """原子写回清单(ensure_ascii=False 保留中文分类名可读)。"""
    s = settings or Settings()
    RegistryStore(s.registry_path).save(reg)
