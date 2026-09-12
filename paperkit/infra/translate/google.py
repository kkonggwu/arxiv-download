"""Google 免费网页接口后端。

免认证、无需 Key,用的是 Chrome 划词词典那条通道。属于非公开接口、没有
SLA,可能随时限流或失效,适合个人轻量使用。
"""

import json
import urllib.parse

from ..http import http_get
from .base import split_for_translate


class GoogleTranslator:
    name = "google"

    def __init__(self, url: str, proxy: str | None = None,
                 timeout: int = 30) -> None:
        self.url = url
        self.proxy = proxy
        self.timeout = timeout

    def translate(self, text: str) -> str:
        """返回格式有两种形态(纯字符串数组 / sentences 对象),都做兼容。"""
        out = []
        for piece in split_for_translate(text):
            url = self.url + urllib.parse.quote(piece)
            data = json.loads(
                http_get(url, timeout=self.timeout, proxy=self.proxy)
                .decode("utf-8"))
            if isinstance(data, list):
                out.append("".join(x if isinstance(x, str) else x[0]
                                   for x in data))
            elif isinstance(data, dict):
                out.append(data.get("sentences", [{}])[0].get("trans", ""))
        return "".join(out).strip()
