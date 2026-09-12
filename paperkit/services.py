"""Application-service facades used by integrations and future CLI commands."""

from . import core


def download_paper(arxiv_id: str, destination, *, force: bool = False) -> str:
    return core.download_pdf(arxiv_id, destination, force=force)


def build_bilingual(arxiv_id: str, registry: dict, *, download_images: bool = True):
    return core.build_bilingual(arxiv_id, registry, download_images=download_images)
