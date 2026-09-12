"""OpenAI 兼容后端。

可指向任何实现了 /chat/completions 的服务:OpenAI / DeepSeek / 通义 /
vLLM / Ollama 等。需要 API Key,质量与稳定性比免费接口可控。
"""

import json

from ...errors import TranslateError
from ..http import http_post_json
from .base import split_for_translate

SYSTEM_PROMPT = ("你是学术论文翻译助手。把用户给出的英文段落译成简体中文:"
                 "保持学术语气,术语准确,不要增删内容,不要解释或加注,"
                 "只输出译文本身。")


class OpenAITranslator:
    name = "openai"

    def __init__(self, base_url: str, model: str, api_key: str | None,
                 proxy: str | None = None, chunk_limit: int = 4000,
                 timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.proxy = proxy
        self.chunk_limit = chunk_limit
        self.timeout = timeout

    def translate(self, text: str) -> str:
        """temperature=0 保证可复现;系统提示把模型约束成「只输出译文」。"""
        if not self.api_key:
            raise TranslateError(
                "openai 后端需要 TRANSLATE_API_KEY(或 --translate-api-key)")
        url = self.base_url + "/chat/completions"
        out = []
        for piece in split_for_translate(text, limit=self.chunk_limit):
            payload = {
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": piece},
                ],
            }
            raw = http_post_json(url, payload,
                                 {"Authorization": f"Bearer {self.api_key}"},
                                 timeout=self.timeout, proxy=self.proxy)
            data = json.loads(raw.decode("utf-8"))
            out.append(data["choices"][0]["message"]["content"].strip())
        return "".join(out)
