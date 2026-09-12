"""翻译缓存。

两条硬规则,都是踩过坑之后定下来的:

1. **只有成功的译文才写进缓存。** 早期版本把 "⚠ 翻译失败: ..." 也写进去,
   重跑时该 key 已存在 → 被当成「已翻译」而永远跳过,一次网络抖动就留下
   永久疤痕。现在失败只记在内存里,本次渲染标 ⚠,重跑自动重试。
2. **增量落盘。** 一篇 270 段的论文要跑好几分钟,中途中断(Ctrl-C、断网、
   限流卡死)不该把已翻好的部分全部丢掉,所以每 flush_every 段落盘一次。

另外会在载入时清理历史遗留的失败占位(带 fail_mark 前缀的值),把老缓存里
的疤痕一并抹掉。
"""

import json
from pathlib import Path

from .storage import write_text_atomic


class TranslationCache:
    """以「英文原文」为 key 的翻译缓存。

    key 用原文而不是序号,是为了改输出格式、扩充纠错词条都不用重新翻译——
    重跑秒级完成。
    """

    def __init__(self, path: Path, flush_every: int = 20,
                 fail_mark: str = "⚠") -> None:
        self.path = path
        self.flush_every = flush_every
        self.fail_mark = fail_mark
        self.pruned = 0            # 本次清理掉的历史失败条目数
        self._data: dict[str, str] = {}
        self._pending = 0          # 距上次落盘又新增了多少条

    # ---- 载入 ----
    def load(self) -> "TranslationCache":
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        stale = [k for k, v in self._data.items()
                 if isinstance(v, str) and v.startswith(self.fail_mark)]
        for k in stale:
            del self._data[k]
        self.pruned = len(stale)
        return self

    # ---- 读写 ----
    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, key: str) -> str:
        return self._data[key]

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def put(self, key: str, value: str) -> None:
        """写入一条**成功**的译文。只应由成功路径调用。"""
        self._data[key] = value
        self._pending += 1
        if self.flush_every and self._pending % self.flush_every == 0:
            self.flush()

    # ---- 落盘 ----
    def flush(self) -> None:
        write_text_atomic(self.path, json.dumps(self._data,
                                                ensure_ascii=False))
        self._pending = 0

    @property
    def data(self) -> dict[str, str]:
        """只读视图,供渲染阶段查询(不要用它写)。"""
        return self._data
