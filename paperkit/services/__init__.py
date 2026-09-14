"""应用服务层:编排用例,持有事务边界。

依赖方向约束(由 tests/test_layering.py 在 CI 层强制):
    services 可以依赖 domain / infra / config / errors
    services **不得**依赖 cli
"""

from .bilingual import build_bilingual, is_generated, target_ids
from .download import download_entry, download_pdf, ensure_metadata, resolve_entry
from .images import asset_relpath, localize_images
from .listing import paper_rows, summary_line
from .registry import load_registry, save_registry

# 兼容原有对外名字(原 paperkit/services.py 的 API)
download_paper = download_pdf

__all__ = [
    "build_bilingual", "is_generated", "target_ids",
    "download_paper", "download_pdf", "download_entry",
    "ensure_metadata", "resolve_entry",
    "asset_relpath", "localize_images",
    "paper_rows", "summary_line",
    "load_registry", "save_registry",
]
