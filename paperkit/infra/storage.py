"""文件系统边界:登记表读写与生成文本的原子落盘。

只有一件事值得强调——原子写。翻译缓存每 20 段落盘一次,而「Ctrl-C / 断网 /
限流卡死」恰恰是这个项目的高频中断场景:非原子写一旦在写入瞬间被打断,
缓存会变成半截 JSON,下次 json.loads 直接抛异常,整篇已翻好的进度全废。
"""

import json
from pathlib import Path


def write_text_atomic(path: Path, text: str) -> None:
    """经同目录临时文件写入 UTF-8 文本,再原子替换目标文件。

    同目录是必须的:跨文件系统时 os.replace 会退化成「复制 + 删除」,就失去
    原子性了。Path.replace 在 Windows 上走 os.replace,同样是原子的。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():          # 写入或替换失败时别留下垃圾
            tmp.unlink()


class RegistryStore:
    """papers.json 的读写。

    登记表是「哪些论文已落盘、元数据补全了没有」的唯一依据,因此写入必须
    原子;读不到文件时返回空骨架,首次使用无需手工创建。
    """

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"papers": []}

    def save(self, registry: dict) -> None:
        # ensure_ascii=False 保留中文分类名可读;indent=2 方便人工查看和手改
        write_text_atomic(
            self.path, json.dumps(registry, ensure_ascii=False, indent=2) + "\n"
        )
