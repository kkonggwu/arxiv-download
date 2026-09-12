"""控制台日志。

为什么不用标准库 logging:这个工具的日志就是给人看的进度条(「翻译进度
3/270」「图片:新增 20 张」),不需要分级、handler、formatter 那一套;
而且有一条硬需求——Windows 控制台默认 GBK,直接 print "✓"/"⚠" 会抛
UnicodeEncodeError 把整个批量任务打断。这里用 try/except 兜住并按控制台
实际编码降级替换,比配置 logging handler 更直接、也更可测
(见 tests/domain 之外的 TestLogging)。
"""

import sys


def log(msg: str) -> None:
    """flush=True 让输出立刻上屏——批量任务里能实时看到进度。"""
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        # 直接调用业务函数时可能还没经过 CLI 的 UTF-8 配置。
        # 按控制台实际编码替换无法表示的符号，避免任务因日志中断。
        # TextIOWrapper.write() 会先编码整串再落盘，异常发生在写入前，
        # 所以这里不会留下半行输出。
        stream = sys.stdout
        encoding = getattr(stream, "encoding", None) or "utf-8"
        text = msg.encode(encoding, errors="replace").decode(encoding)
        stream.write(text + "\n")
        stream.flush()
