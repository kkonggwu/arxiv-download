"""插图本地化:把 Markdown 里的图片链接下载到本地,改成相对路径引用。

图片统一落到 papers/双语/assets/<id>/<原相对路径>,正文用相对于 md 的
`../assets/...` 引用——和 PDF、翻译缓存一样全本地,断网也能看图。

两个必须注意的点:
  * 围栏代码块内的行要跳过。代码块装的是 prompt 模板/清单原文,里面若恰好
    出现 `![x](y)` 这种字样,会被误当成图片链接改写。
  * download=False 时只把相对路径补全成绝对 URL(对应 --no-images),
    用于离线场景:不下载,但链接仍然是通的。

单张失败时退回绝对 URL(链接至少是通的),不因为一张图失败就中断整篇。
"""

import re
import urllib.parse
from pathlib import Path

from ..config import Settings
from ..domain import sanitize
from ..infra.http import http_get
from ..infra.logging import log

IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"\s*(`{3,}|~{3,})")


def asset_relpath(abs_url: str) -> Path:
    """从图片绝对 URL 推出它在 assets/ 下的相对路径。

    arxiv: /html/2501.12948v2/plot.svg     → 2501.12948v2/plot.svg
    ar5iv: /html/1706.03762/assets/x.svg   → 1706.03762/assets/x.svg
    保留原有的目录层级,既避免同名文件互相覆盖,也便于对照原始来源。
    """
    path = urllib.parse.urlparse(abs_url).path.lstrip("/")
    if path.startswith("html/"):      # ar5iv 的路径带这个前缀,去掉更清爽
        path = path[len("html/"):]
    parts = [sanitize(p) for p in path.split("/") if p not in ("", ".", "..")]
    parts = [p for p in parts if p]
    return Path(*parts) if parts else Path("image")


def localize_images(lines: list[str], arxiv_id: str, base: str,
                    settings: Settings | None = None,
                    download: bool = True) -> list[str]:
    """就地改写 Markdown 行里的图片链接。

    已存在的文件直接复用,不重复请求;表格单元格里内联的图片走的是同一套
    替换,所以这里对整个 md 行做正则,而不是只处理 image 区块。
    """
    s = settings or Settings()
    dest_root = s.assets_dir(arxiv_id)
    mapping: dict[str, str] = {}
    stats = {"new": 0, "reused": 0, "failed": 0}

    def repl(match: re.Match) -> str:
        alt, url = match.group(1), match.group(2)
        if url.startswith(("http://", "https://", "data:")):
            return match.group(0)          # 已经是绝对地址,不动
        if url in mapping:
            return f"![{alt}]({mapping[url]})"

        abs_url = urllib.parse.urljoin(base, url)
        if not download:
            mapping[url] = abs_url
            return f"![{alt}]({abs_url})"

        rel = asset_relpath(abs_url)
        dest = dest_root / rel
        local = f"../assets/{arxiv_id}/{rel.as_posix()}"

        if dest.exists() and dest.stat().st_size > 0:
            stats["reused"] += 1
            mapping[url] = local
            return f"![{alt}]({local})"
        try:
            data = http_get(abs_url, timeout=60, proxy=s.proxy)
            head = data[:200].lstrip().lower()
            if not data or head.startswith((b"<!doctype html", b"<html")):
                raise ValueError("返回的不是图片(可能被限流或 404)")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            stats["new"] += 1
            mapping[url] = local
            return f"![{alt}]({local})"
        except Exception as e:
            log(f"  ! 图片下载失败 {url}: {e}")
            stats["failed"] += 1
            mapping[url] = abs_url
            return f"![{alt}]({abs_url})"

    out: list[str] = []
    fence: str | None = None               # 当前围栏标记的字符,None=不在围栏内
    for line in lines:
        marker = FENCE_RE.match(line)
        if marker:
            char = marker.group(1)[0]
            if fence is None:
                fence = char
            elif fence == char:
                fence = None
            out.append(line)               # 围栏行本身原样保留
            continue
        out.append(line if fence else IMAGE_RE.sub(repl, line))

    if stats["new"] or stats["failed"] or stats["reused"]:
        log(f"  图片:新增 {stats['new']} 张、复用 {stats['reused']} 张、"
            f"失败 {stats['failed']} 张 → {dest_root.relative_to(s.base_dir)}")
    elif not download and mapping:
        log(f"  图片:按 --no-images 跳过下载,{len(mapping)} 张改为绝对链接")
    return out
