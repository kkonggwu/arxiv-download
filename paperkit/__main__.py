"""让 `python -m paperkit` 可用,与 `papers` / `fetch_papers.py` 等价。"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
