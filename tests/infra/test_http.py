"""HTTP 客户端:代理注入与请求构造。

proxy 从模块级全局改成显式参数,因此同一进程内可以同时用两种代理,
测试也不必再改全局。
"""

import json
import unittest
import urllib.request
from unittest import mock

from tests.helpers import bootstrap  # noqa: F401
from paperkit.infra.http import UrllibTransport, http_get, http_post_json


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestHttpGet(unittest.TestCase):
    def test_no_proxy_uses_urlopen(self):
        with mock.patch.object(urllib.request, "urlopen",
                               return_value=_FakeResponse(b"ok")) as g:
            self.assertEqual(http_get("https://x/"), b"ok")
        self.assertEqual(g.call_count, 1)

    def test_proxy_uses_a_proxy_handler_opener(self):
        opener = mock.MagicMock()
        opener.open.return_value = _FakeResponse(b"via-proxy")
        with mock.patch.object(urllib.request, "build_opener",
                               return_value=opener) as bo, \
             mock.patch.object(urllib.request, "urlopen") as direct:
            out = http_get("https://x/", proxy="http://127.0.0.1:7897")
        self.assertEqual(out, b"via-proxy")
        self.assertFalse(direct.called)          # 不能绕过代理直连
        handler = bo.call_args.args[0]
        self.assertIsInstance(handler, urllib.request.ProxyHandler)

    def test_user_agent_is_set(self):
        with mock.patch.object(urllib.request, "urlopen",
                               return_value=_FakeResponse(b"ok")) as g:
            http_get("https://x/")
        req = g.call_args.args[0]
        # urllib 会把 header 名规范成 User-agent
        self.assertEqual(req.get_header("User-agent"),
                         "paper-fetcher/0.1 (personal study use)")


class TestHttpPostJson(unittest.TestCase):
    def test_body_is_json_and_method_is_post(self):
        with mock.patch.object(urllib.request, "urlopen",
                               return_value=_FakeResponse(b"{}")) as g:
            http_post_json("https://x/", {"a": 1})
        req = g.call_args.args[0]
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(json.loads(req.data.decode()), {"a": 1})

    def test_extra_headers_are_merged(self):
        with mock.patch.object(urllib.request, "urlopen",
                               return_value=_FakeResponse(b"{}")) as g:
            http_post_json("https://x/", {}, {"Authorization": "Bearer sk"})
        req = g.call_args.args[0]
        self.assertEqual(req.headers["Authorization"], "Bearer sk")
        self.assertEqual(req.headers["Content-type"], "application/json")

    def test_proxy_is_honoured(self):
        opener = mock.MagicMock()
        opener.open.return_value = _FakeResponse(b"{}")
        with mock.patch.object(urllib.request, "build_opener",
                               return_value=opener), \
             mock.patch.object(urllib.request, "urlopen") as direct:
            http_post_json("https://x/", {}, proxy="http://p:1")
        self.assertFalse(direct.called)


class TestTransportProtocol(unittest.TestCase):
    def test_urllib_transport_satisfies_the_protocol_shape(self):
        t = UrllibTransport(proxy=None)
        self.assertTrue(callable(t.get))
        self.assertTrue(callable(t.post_json))

    def test_transport_binds_proxy_at_construction(self):
        t = UrllibTransport(proxy="http://p:1")
        self.assertEqual(t.proxy, "http://p:1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
