"""日志:Windows GBK 控制台不能因 ✓/⚠ 打断任务。"""

import io
import unittest
from unittest import mock

from paperkit.infra.logging import log
from tests.helpers import bootstrap  # noqa: F401


class TestLogging(unittest.TestCase):
    def test_log_replaces_unencodable_console_characters(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="gbk")
        with mock.patch("sys.stdout", stream):
            log("✓ 已生成")
            stream.flush()
        self.assertEqual(stream.buffer.getvalue().decode("gbk").splitlines(),
                         ["? 已生成"])

    def test_utf8_console_keeps_the_symbol(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with mock.patch("sys.stdout", stream):
            log("✓ 已生成")
            stream.flush()
        self.assertEqual(stream.buffer.getvalue().decode("utf-8").splitlines(),
                         ["✓ 已生成"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
