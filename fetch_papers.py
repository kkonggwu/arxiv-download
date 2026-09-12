#!/usr/bin/env python3
"""兼容入口。

实现已迁移到 paperkit 包,这里只做转发,等价于 `papers` 或 `python -m paperkit`。
保留这个文件是为了让 README 里所有 `python fetch_papers.py ...` 命令继续可用。
"""

import sys
from pathlib import Path

# 允许从任意工作目录直接运行本文件
sys.path.insert(0, str(Path(__file__).resolve().parent))

from paperkit.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
