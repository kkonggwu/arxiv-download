"""Runtime configuration assembled by the CLI boundary."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    proxy: str | None = None
    translate_backend: str = "google"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    translate_api_key: str | None = None

    @classmethod
    def from_values(cls, *, proxy: str | None = None,
                    translator: str | None = None,
                    base_url: str | None = None,
                    model: str | None = None,
                    api_key: str | None = None) -> "Settings":
        return cls(
            proxy=proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
            translate_backend=(translator or os.environ.get("TRANSLATE_BACKEND")
                               or "google").strip().lower(),
            openai_base_url=(base_url or os.environ.get("TRANSLATE_BASE_URL")
                             or "https://api.openai.com/v1"),
            openai_model=(model or os.environ.get("TRANSLATE_MODEL")
                          or "gpt-4o-mini"),
            translate_api_key=api_key or os.environ.get("TRANSLATE_API_KEY"),
        )
