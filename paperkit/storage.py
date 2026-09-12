"""Filesystem boundary for registry and generated text artifacts."""

import json
from pathlib import Path


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


class RegistryStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"papers": []}

    def save(self, registry: dict) -> None:
        write_text_atomic(
            self.path, json.dumps(registry, ensure_ascii=False, indent=2) + "\n"
        )
