"""arXiv 的元数据与 HTML 抓取。

这个模块负责**所有**对 arXiv 的读取,并在这里把「网络失败」翻译成语义化
的异常:拿不到 HTML 版抛 SourceUnavailable(不可重试),而不是笼统的
RuntimeError——批量任务据此决定是跳过还是重试。
"""

import re
import xml.etree.ElementTree as ET

from ..config import Settings
from ..errors import SourceUnavailable
from .http import http_get
from .logging import log

ATOM = "{http://www.w3.org/2005/Atom}"   # arXiv API 返回的 XML 命名空间前缀


def fetch_metadata(arxiv_id: str, settings: Settings | None = None) -> dict | None:
    """通过 arXiv Atom API 拿标题/作者/年份;取不到时返回 None。

    API 一次可查多篇,这里简单起见逐篇查。网络失败不抛异常,而是返回 None,
    由调用方决定怎么办——**关键是不能降级成占位文件名**:
    文件名一旦按占位值写进登记表,`--all` 的补全条件("file" 不存在)就不再
    成立,这篇论文会被永久钉死在错误的名字上(实测过一次网络抖动就会留下
    `- Unknown - <id> [<id>].pdf` 这种名字,而且再也改不回来)。
    """
    s = settings or Settings()
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        root = ET.fromstring(http_get(url, proxy=s.proxy))
        entry = root.find(f"{ATOM}entry")
        if entry is None:
            raise ValueError("entry not found")
        # 标题里的换行/多空格压成一个空格,否则文件名会断裂
        title = re.sub(r"\s+", " ", entry.findtext(f"{ATOM}title", "").strip())
        if not title:
            raise ValueError("title 为空")
        # arXiv API 偶尔会重复返回同一个作者——实测 2501.12948 返回 200 个名字,
        # 其中 'Shengfeng Ye'、'Yanhong Xu' 各出现两次。按首次出现顺序去重。
        seen: set[str] = set()
        authors = []
        for node in entry.findall(f"{ATOM}author"):
            name = node.findtext(f"{ATOM}name", "").strip()
            if name and name not in seen:
                seen.add(name)
                authors.append(name)
        published = entry.findtext(f"{ATOM}published", "")[:4]  # '2025-01-...' -> '2025'
        return {"title": title, "authors": authors,
                "year": published or "unknown", "id": arxiv_id}
    except Exception as e:
        log(f"  ! 元数据获取失败({e})")
        return None


def fetch_paper_html(arxiv_id: str,
                     settings: Settings | None = None) -> tuple[str, str, str]:
    """抓取论文 HTML 版,优先 arXiv 原生,失败退回 ar5iv。

    返回 (html, 来源名, 图片基址)。基址必须跟着来源走,因为两个源的图片
    相对路径格式不同,拼错就是 404:
      arxiv: data="2501.12948v2/plot.svg"            → https://arxiv.org/html/
      ar5iv: data="/html/2501.12948/assets/plot.svg" → https://ar5iv.labs.arxiv.org

    arXiv 官方 HTML 只有 2024 年初以后的论文;更早的由 ar5iv(公益项目,
    同样是 LaTeXML 渲染)兜底。两个源的 HTML 结构相同,后面解析无差别。
    """
    s = settings or Settings()
    sources = [
        (f"https://arxiv.org/html/{arxiv_id}", "arxiv",
         "https://arxiv.org/html/"),
        (f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}", "ar5iv",
         "https://ar5iv.labs.arxiv.org"),
    ]
    last_err = None
    for url, name, base in sources:
        try:
            html = http_get(url, timeout=90, proxy=s.proxy).decode(
                "utf-8", errors="replace")
            if "<p" in html or "ltx_" in html:  # 粗验:页面确实有正文
                return html, name, base
            last_err = f"{name}: 页面无正文"
        except Exception as e:
            last_err = f"{name}: {e}"
    raise SourceUnavailable(
        f"拿不到 HTML 版({last_err});纯扫描版 PDF 无法自动提取")
