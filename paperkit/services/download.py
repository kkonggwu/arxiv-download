"""下载用例:登记条目 → 拉元数据 → 下载 PDF → 回写登记表。

这里有一条贯穿全模块的不变式,踩过一次坑之后不敢再犯:

    **元数据拿不到时,绝不写 `file` 字段。**

因为 `--all` 判断「要不要补全」的依据就是 `"file" not in entry`。一旦写进
占位文件名(如 `- Unknown - 2501.12948 [2501.12948].pdf`),这个条件永远为假,
该条目会被永久钉死在错误的名字上,再也补不回来。
"""

from pathlib import Path

from ..config import Settings
from ..domain import make_filename, parse_arxiv_id, sanitize
from ..infra.arxiv_api import fetch_metadata
from ..infra.http import http_get
from ..infra.logging import log


def download_pdf(arxiv_id: str, dest: Path, settings: Settings | None = None,
                 force: bool = False) -> str:
    """下载单篇 PDF;返回 'downloaded' / 'skipped' / 'failed' 三态。

    已存在即跳过 = 断点续传;校验 %PDF 魔数防止把限流 HTML 存成 .pdf;
    失败时清掉写了一半的空文件,不留垃圾。
    """
    s = settings or Settings()
    if dest.exists() and not force:
        return "skipped"
    url = f"https://arxiv.org/pdf/{arxiv_id}"
    try:
        data = http_get(url, timeout=120, proxy=s.proxy)
        if not data.startswith(b"%PDF"):
            raise ValueError("响应不是 PDF(可能被限流)")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return "downloaded"
    except Exception as e:
        log(f"  ! 下载失败 {arxiv_id}: {e}")
        if dest.exists() and dest.stat().st_size == 0:
            dest.unlink()
        return "failed"


def resolve_entry(text: str, category: str | None,
                  settings: Settings | None = None) -> dict | None:
    """把命令行输入(id 或 URL)解析成一条完整的登记条目。

    元数据取不到时返回**只含 id + category** 的条目(没有 file 字段):
    条目照样进登记表,但这次不下载,下次 `--all` 会把元数据和 PDF 一起补上。
    绝不能退而求其次用占位名先落盘——那样登记表就再也补不回来了。
    """
    s = settings or Settings()
    arxiv_id = parse_arxiv_id(text)
    if not arxiv_id:
        log(f"! 无法识别: {text} (需要 arXiv id 或 arxiv.org 链接)")
        return None
    log(f"* 拉取元数据 {arxiv_id} ...")
    meta = fetch_metadata(arxiv_id, s)
    cat = category or "未分类"
    if meta is None:
        log("  ! 元数据未取到:先只登记 id 与分类,下次 --all 自动补全")
        return {"id": arxiv_id, "category": cat}
    return {**meta, "category": cat, "file": make_filename(meta)}


def ensure_metadata(entry: dict, settings: Settings | None = None) -> bool:
    """给只登记了 id 的条目补全元数据与文件名;成功返回 True。

    失败时**原样返回 False、不碰 entry**:尤其是绝不写 `file` 字段。
    因为 --all 判断"要不要补全"的依据就是 `"file" not in entry`,
    一旦写进占位文件名,这个条目就再也补不回来了。
    """
    s = settings or Settings()
    meta = fetch_metadata(entry["id"], s)
    if meta is None:
        return False
    entry.update(meta)
    entry["category"] = entry.get("category", "未分类")
    entry["file"] = make_filename(entry)
    return True


def download_entry(entry: dict, settings: Settings | None = None,
                   force: bool = False) -> str:
    """按条目的分类建目录、下载 PDF,并打一行状态日志。"""
    s = settings or Settings()
    target_dir = s.out_dir / sanitize(entry["category"])
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / entry["file"]
    status = download_pdf(entry["id"], dest, s, force=force)
    size = f"({dest.stat().st_size / 1024:.0f} KB)" if dest.exists() else ""
    log(f"  {'✓' if status == 'downloaded' else '−' if status == 'skipped' else '✗'} "
        f"{entry['category']}/{entry['file']} {size}")
    return status
