"""HTTP 客户端(标准库 urllib,零第三方依赖)。

代理的处理是这里的核心。Python 标准库对代码里设的代理环境变量语义并不可靠,
所以显式构造 ProxyHandler,保证 --proxy 参数对**每一个**请求都生效——arXiv
直连常被阻断,代理不通这个工具基本没法用。

重构前 proxy 是模块级全局 PROXY,由 main() 用 global 语句改写。现在它是
每次调用的显式参数,因此同一个进程里可以同时用两种代理(或不用代理)请求,
测试也不必再改全局。
"""

import json
import urllib.parse
import urllib.request
from typing import Protocol

from ..errors import NetworkError

UA = {"User-Agent": "paper-fetcher/0.1 (personal study use)"}


class Transport(Protocol):
    """HTTP 传输接口。services 层依赖这个协议而非具体实现,便于注入假实现。"""

    def get(self, url: str, timeout: int = 60) -> bytes: ...

    def post_json(self, url: str, payload: dict,
                  headers: dict | None = None, timeout: int = 60) -> bytes: ...


class UrllibTransport:
    """基于 urllib 的默认实现。proxy 在构造时绑定,一次构造可用于多个请求。"""

    def __init__(self, proxy: str | None = None,
                 user_agent: dict | None = None) -> None:
        self.proxy = proxy
        self.user_agent = user_agent or UA

    def _open(self, req: urllib.request.Request, timeout: int):
        if self.proxy:
            handler = urllib.request.ProxyHandler(
                {"http": self.proxy, "https": self.proxy})
            return urllib.request.build_opener(handler).open(req, timeout=timeout)
        return urllib.request.urlopen(req, timeout=timeout)

    def get(self, url: str, timeout: int = 60) -> bytes:
        req = urllib.request.Request(url, headers=self.user_agent)
        with self._open(req, timeout) as resp:
            return resp.read()

    def post_json(self, url: str, payload: dict,
                  headers: dict | None = None, timeout: int = 60) -> bytes:
        body = json.dumps(payload).encode("utf-8")
        hdrs = {"Content-Type": "application/json", **self.user_agent,
                **(headers or {})}
        req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
        with self._open(req, timeout) as resp:
            return resp.read()


def http_get(url: str, timeout: int = 60, proxy: str | None = None) -> bytes:
    """发 GET 请求返回响应体;传了 proxy 时所有流量都走代理。"""
    return UrllibTransport(proxy).get(url, timeout=timeout)


def http_post_json(url: str, payload: dict, headers: dict | None = None,
                   timeout: int = 60, proxy: str | None = None) -> bytes:
    """发 JSON POST 返回响应体。代理设置与 http_get 保持一致。

    供 OpenAI 兼容的翻译后端使用;调用方自己解析返回的 JSON。
    """
    return UrllibTransport(proxy).post_json(url, payload, headers=headers,
                                            timeout=timeout)


__all__ = ["Transport", "UrllibTransport", "http_get", "http_post_json",
           "NetworkError", "UA"]
