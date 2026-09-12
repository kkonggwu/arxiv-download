#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论文下载脚手架(仅依赖 Python 标准库,无需 pip 安装任何东西)。

整体架构:
    papers.json (清单数据库)
        │  id + category,下载后自动补全 标题/作者/年份/文件名
        ▼
    ┌─ --all / 位置参数 ──→ arXiv API 拿元数据 ──→ papers/<分类>/*.pdf
    │
    └─ --bilingual ──→ 抓 HTML 版 ──→ 解析成段落 ──→ 逐段翻译(有缓存)
                                   ──→ papers/双语/<分类>/ID 中英对照.md

用法:
  python fetch_papers.py <arxiv_id|url> [<more>...] [--category 分类名]
      下载指定论文到 papers/<分类>/,并登记到 papers.json
      例: python fetch_papers.py 1706.03762 --category 经典
          python fetch_papers.py https://arxiv.org/abs/2501.12948

  python fetch_papers.py --all
      下载 papers.json 中所有尚未落盘的论文(已存在的自动跳过,可反复重跑)

  python fetch_papers.py --bilingual <id|all> [--translator google|openai]
      生成中英对照阅读材料到 papers/双语/

  python fetch_papers.py --list
      查看清单及下载状态([✓]=PDF已下载 [◈]=对照材料已生成)

说明:
  * --force 可强制重新下载;--proxy 指定 HTTP 代理(直连 arXiv 常被阻断)。
  * 文件名自动取 arXiv 元数据,格式: 年份 - 第一作者 et al. - 标题 [id].pdf
  * 对 arXiv 的请求间隔 3 秒,遵守其限流要求。
  * 翻译后端默认 google(免 Key 的免费网页接口);需要更稳定的质量时用
    --translator openai 配合 --translate-base-url / --translate-model /
    TRANSLATE_API_KEY,可指向任何 OpenAI 兼容服务。不同后端各用一份缓存。
  * 译文只有成功才写缓存;失败的段落本次标 ⚠,重跑会自动重试。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from .config import Settings
from .domain import (PaperHTMLParser, SECTION_ZH, fix_acronyms, heading_level,  # noqa: F401
                     make_filename, parse_arxiv_id, parse_blocks,
                     render_code_block, render_equation_rows, render_table,
                     sanitize)
from .infra.http import http_get as _http_get
from .infra.http import http_post_json as _http_post_json
from .infra.logging import log
from .infra.storage import write_text_atomic

# ---------------------------------------------------------------------------
# 全局路径与常量(全部相对脚本所在目录,挪动整个文件夹也不受影响)
# ---------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent.parent # 项目根目录
REGISTRY = BASE / "papers.json"              # 论文登记表
OUTDIR = BASE / "papers"                     # PDF 与对照材料的根目录
ATOM = "{http://www.w3.org/2005/Atom}"       # arXiv API 返回的 XML 命名空间前缀

UA = {"User-Agent": "paper-fetcher/0.1 (personal study use)"}
PROXY = None  # 形如 http://127.0.0.1:7897,由 --proxy 或环境变量 HTTPS_PROXY 设置


# ---------------------------------------------------------------------------
# 基础工具:HTTP(带代理)
#
# 实现已移入 paperkit.infra.http,这里保留一层薄适配:把当前生效的 PROXY
# 注入进去。之所以不直接 `from ... import http_get` 后就用,是为了让本模块
# 内部对 http_get 的调用仍然走模块全局查找——现有测试用
# mock.patch.object(fp, "http_get") 打桩,这样才继续生效。
# 等 P3 把编排逻辑移进 services 层、PROXY 全局消失后,这层适配即可删除。
# ---------------------------------------------------------------------------
def http_get(url: str, timeout: int = 60) -> bytes:
    """发 GET 请求返回响应体;设置了 PROXY 时所有流量都走代理。"""
    return _http_get(url, timeout=timeout, proxy=PROXY)


def http_post_json(url: str, payload: dict, headers: dict | None = None,
                   timeout: int = 60) -> bytes:
    """发 JSON POST 返回响应体。代理设置与 http_get 保持一致。"""
    return _http_post_json(url, payload, headers=headers, timeout=timeout,
                           proxy=PROXY)


# ---------------------------------------------------------------------------
# 登记表(papers.json)的读写
# ---------------------------------------------------------------------------
def load_registry() -> dict:
    """读清单;文件不存在时返回空骨架,首次使用无需手工创建。"""
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {"papers": []}


def save_registry(reg: dict) -> None:
    """ensure_ascii=False 保留中文分类名可读;indent=2 方便人工查看和手改。"""
    write_text_atomic(REGISTRY,
                      json.dumps(reg, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------------------
# arXiv 元数据
# ---------------------------------------------------------------------------


def fetch_metadata(arxiv_id: str) -> dict | None:
    """通过 arXiv Atom API 拿标题/作者/年份;取不到时返回 None。

    API 一次可查多篇,这里简单起见逐篇查。网络失败不抛异常,而是返回 None,
    由调用方决定怎么办——**关键是不能降级成占位文件名**:
    文件名一旦按占位值写进登记表,`--all` 的补全条件("file" 不存在)就不再
    成立,这篇论文会被永久钉死在错误的名字上(实测过一次网络抖动就会留下
    `- Unknown - <id> [<id>].pdf` 这种名字,而且再也改不回来)。
    """
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        root = ET.fromstring(http_get(url))
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


# ---------------------------------------------------------------------------
# PDF 下载
# ---------------------------------------------------------------------------
def download_pdf(arxiv_id: str, dest: Path, force: bool = False) -> str:
    """下载单篇 PDF;返回 'downloaded' / 'skipped' / 'failed' 三态。

    已存在即跳过 = 断点续传;校验 %PDF 魔数防止把限流 HTML 存成 .pdf;
    失败时清掉写了一半的空文件,不留垃圾。
    """
    if dest.exists() and not force:
        return "skipped"
    url = f"https://arxiv.org/pdf/{arxiv_id}"
    try:
        data = http_get(url, timeout=120)
        if not data.startswith(b"%PDF"):
            raise ValueError("响应不是 PDF(可能被限流)")
        dest.write_bytes(data)
        return "downloaded"
    except Exception as e:
        log(f"  ! 下载失败 {arxiv_id}: {e}")
        if dest.exists() and dest.stat().st_size == 0:
            dest.unlink()
        return "failed"


def resolve_entry(text: str, category: str | None) -> dict | None:
    """把命令行输入(id 或 URL)解析成一条完整的登记条目。

    元数据取不到时返回**只含 id + category** 的条目(没有 file 字段):
    条目照样进登记表,但这次不下载,下次 `--all` 会把元数据和 PDF 一起补上。
    绝不能退而求其次用占位名先落盘——那样登记表就再也补不回来了。
    """
    arxiv_id = parse_arxiv_id(text)
    if not arxiv_id:
        log(f"! 无法识别: {text} (需要 arXiv id 或 arxiv.org 链接)")
        return None
    log(f"* 拉取元数据 {arxiv_id} ...")
    meta = fetch_metadata(arxiv_id)
    cat = category or "未分类"
    if meta is None:
        log(f"  ! 元数据未取到:先只登记 id 与分类,下次 --all 自动补全")
        return {"id": arxiv_id, "category": cat}
    return {**meta, "category": cat, "file": make_filename(meta)}


def ensure_metadata(entry: dict) -> bool:
    """给只登记了 id 的条目补全元数据与文件名;成功返回 True。

    失败时**原样返回 False、不碰 entry**:尤其是绝不写 `file` 字段。
    因为 --all 判断"要不要补全"的依据就是 `"file" not in entry`,
    一旦写进占位文件名,这个条目就再也补不回来了。
    """
    meta = fetch_metadata(entry["id"])
    if meta is None:
        return False
    entry.update(meta)
    entry["category"] = entry.get("category", "未分类")
    entry["file"] = make_filename(entry)
    return True


def download_entry(entry: dict, force: bool = False) -> str:
    """按条目的分类建目录、下载 PDF,并打一行状态日志。"""
    target_dir = OUTDIR / sanitize(entry["category"])
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / entry["file"]
    status = download_pdf(entry["id"], dest, force=force)
    size = f"({dest.stat().st_size / 1024:.0f} KB)" if dest.exists() else ""
    log(f"  {'✓' if status == 'downloaded' else '−' if status == 'skipped' else '✗'} "
        f"{entry['category']}/{entry['file']} {size}")
    return status


# ---------------------------------------------------------------------------
# 中英对照阅读材料(--bilingual)
#
# 流程:抓论文 HTML 版 → 解析成 (标题/段落/图注) 序列 → 逐段机翻(结果
# 落盘缓存) → 交错拼装成 Markdown。公式通过 <math alttext> 还原为 $...$。
# ---------------------------------------------------------------------------
BILINGUAL_DIR = OUTDIR / "双语"
CACHE_DIR = BILINGUAL_DIR / ".cache"
FAIL_MARK = "⚠"      # 译文失败标记;带此标记的缓存条目会被视为未命中并重试
CACHE_FLUSH_EVERY = 20  # 每翻译这么多段就把缓存落盘一次(见 build_bilingual)

# ---- 翻译后端(由 --translator 或 TRANSLATE_BACKEND 选择)------------------
# google: Google 免费网页接口(Chrome 划词词典用的通道),免认证、无需 Key,
#         但属于非公开接口、没有 SLA,可能随时限流或失效,适合个人轻量使用。
# openai: 任意 OpenAI 兼容的 /chat/completions 接口(OpenAI / DeepSeek / 通义 /
#         vLLM / Ollama 等),需要 TRANSLATE_API_KEY,质量与稳定性更可控。
TRANSLATE_BACKEND = "google"
TRANSLATE_RETRIES = 3          # 单段翻译的重试次数(退避 2/4/6 秒)

GOOGLE_TRANSLATE_URL = ("https://clients5.google.com/translate_a/t"
                        "?client=dict-chrome-ex&sl=en&tl=zh-CN&q=")

OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4o-mini"
TRANSLATE_API_KEY = None       # 由 --translate-api-key 或 TRANSLATE_API_KEY 提供

# openai 后端长段一次可以送更多内容,减少被切断的句子,译文衔接更自然。
OPENAI_CHUNK_LIMIT = 4000

def fetch_paper_html(arxiv_id: str) -> tuple[str, str, str]:
    """抓取论文 HTML 版,优先 arXiv 原生,失败退回 ar5iv。

    返回 (html, 来源名, 图片基址)。基址必须跟着来源走,因为两个源的图片
    相对路径格式不同,拼错就是 404:
      arxiv: data="2501.12948v2/plot.svg"            → https://arxiv.org/html/
      ar5iv: data="/html/2501.12948/assets/plot.svg" → https://ar5iv.labs.arxiv.org

    arXiv 官方 HTML 只有 2024 年初以后的论文;更早的由 ar5iv(公益项目,
    同样是 LaTeXML 渲染)兜底。两个源的 HTML 结构相同,后面解析无差别。
    """
    sources = [
        (f"https://arxiv.org/html/{arxiv_id}", "arxiv", "https://arxiv.org/html/"),
        (f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}", "ar5iv",
         "https://ar5iv.labs.arxiv.org"),
    ]
    last_err = None
    for url, name, base in sources:
        try:
            html = http_get(url, timeout=90).decode("utf-8", errors="replace")
            if "<p" in html or "ltx_" in html:  # 粗验:页面确实有正文
                return html, name, base
            last_err = f"{name}: 页面无正文"
        except Exception as e:
            last_err = f"{name}: {e}"
    raise RuntimeError(f"拿不到 HTML 版({last_err});纯扫描版 PDF 无法自动提取")


def _split_for_translate(text: str, limit: int = 1200) -> list[str]:
    """按句子边界把长段切成 ≤limit 的多块。

    翻译接口是 GET 请求,句子要拼进 URL,太长会被服务器拒绝。
    正则 (?<=[.!?;:]) + 在句读符号后面的空格处断开(lookbehind 不消耗字符)。
    """
    if len(text) <= limit:
        return [text]
    pieces, cur = [], ""
    for sent in re.split(r"(?<=[.!?;:]) +", text):
        if len(cur) + len(sent) + 1 > limit and cur:
            pieces.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        pieces.append(cur)
    return pieces


def _translate_google(text: str) -> str:
    """Google 免费网页接口。免 Key,但返回格式有两种形态,都做兼容。"""
    out = []
    for piece in _split_for_translate(text):
        url = GOOGLE_TRANSLATE_URL + urllib.parse.quote(piece)
        data = json.loads(http_get(url, timeout=30).decode("utf-8"))
        if isinstance(data, list):
            out.append("".join(x if isinstance(x, str) else x[0] for x in data))
        elif isinstance(data, dict):
            out.append(data.get("sentences", [{}])[0].get("trans", ""))
    return "".join(out).strip()


def _translate_openai(text: str) -> str:
    """OpenAI 兼容的 /chat/completions 接口(OpenAI / DeepSeek / vLLM / Ollama)。

    用系统提示把模型约束成"只输出译文"的翻译器,temperature=0 保证可复现。
    """
    if not TRANSLATE_API_KEY:
        raise RuntimeError("openai 后端需要 TRANSLATE_API_KEY(或 --translate-api-key)")
    url = OPENAI_BASE_URL.rstrip("/") + "/chat/completions"
    out = []
    for piece in _split_for_translate(text, limit=OPENAI_CHUNK_LIMIT):
        payload = {
            "model": OPENAI_MODEL,
            "temperature": 0,
            "messages": [
                {"role": "system",
                 "content": "你是学术论文翻译助手。把用户给出的英文段落译成简体中文:"
                            "保持学术语气,术语准确,不要增删内容,不要解释或加注,"
                            "只输出译文本身。"},
                {"role": "user", "content": piece},
            ],
        }
        raw = http_post_json(url, payload,
                             {"Authorization": f"Bearer {TRANSLATE_API_KEY}"},
                             timeout=120)
        data = json.loads(raw.decode("utf-8"))
        out.append(data["choices"][0]["message"]["content"].strip())
    return "".join(out)


BACKENDS = {"google": _translate_google, "openai": _translate_openai}


def translate_one(text: str) -> str:
    """翻译一段英文,返回译文;重试若干次后仍失败则抛 RuntimeError。

    公式先替换成 __FORMULA_n__ 占位符,译完再原样还原,避免翻译服务改写
    LaTeX 命令或符号。具体走哪个后端由 TRANSLATE_BACKEND 决定。

    注意:失败必须抛异常而不是返回占位文本——调用方据此决定不写缓存,
    否则一次网络抖动会在缓存里留下永久伤疤。
    """
    # Protect LaTeX from the translation service, which may otherwise remove
    # commands or rewrite symbols. Restore the exact source after translation.
    formulas = []
    def protect(match):
        formulas.append(match.group(0))
        return f" __FORMULA_{len(formulas) - 1}__ "
    protected = re.sub(r"\$\$.*?\$\$|\$[^$\n]+\$", protect, text, flags=re.S)

    backend = BACKENDS.get(TRANSLATE_BACKEND)
    if backend is None:
        raise RuntimeError(f"未知翻译后端: {TRANSLATE_BACKEND}(可选 google/openai)")

    last_err = None
    for attempt in range(TRANSLATE_RETRIES):
        try:
            translated = backend(protected)
            if not translated:
                raise ValueError("后端返回空译文")
            for i, formula in enumerate(formulas):
                translated = translated.replace(f"__FORMULA_{i}__", formula)
            return translated
        except Exception as e:
            last_err = e
            if attempt < TRANSLATE_RETRIES - 1:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"翻译失败: {last_err}")


def _asset_relpath(abs_url: str) -> Path:
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
                    download: bool = True) -> list[str]:
    """把 Markdown 里的图片链接下载到本地并改成相对路径引用。

    图片统一落到 papers/双语/assets/<id>/<原相对路径>,正文用相对于 md 的
    `../assets/...` 引用——和 PDF、翻译缓存一样全本地,断网也能看图。

    已存在的文件直接复用,不重复请求;单张失败时退回绝对 URL(链接至少是
    通的),不因为一张图失败就中断整篇。表格单元格里内联的图片走的是同一套
    替换,所以这里对整个 md 行做正则,而不是只处理 image 区块。

    两个必须注意的点:
      * 围栏代码块内的行要跳过。代码块装的是 prompt 模板/清单原文,
        里面若恰好出现 `![x](y)` 这种字样,会被误当成图片链接改写。
      * download=False 时只把相对路径补全成绝对 URL(对应 --no-images),
        用于离线场景:不下载,但链接仍然是通的。
    """
    pattern = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
    dest_root = BILINGUAL_DIR / "assets" / arxiv_id
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

        rel = _asset_relpath(abs_url)
        dest = dest_root / rel
        local = f"../assets/{arxiv_id}/{rel.as_posix()}"

        if dest.exists() and dest.stat().st_size > 0:
            stats["reused"] += 1
            mapping[url] = local
            return f"![{alt}]({local})"
        try:
            data = http_get(abs_url, timeout=60)
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
        marker = re.match(r"\s*(`{3,}|~{3,})", line)
        if marker:
            char = marker.group(1)[0]
            if fence is None:
                fence = char
            elif fence == char:
                fence = None
            out.append(line)               # 围栏行本身原样保留
            continue
        out.append(line if fence else pattern.sub(repl, line))

    if stats["new"] or stats["failed"] or stats["reused"]:
        log(f"  图片:新增 {stats['new']} 张、复用 {stats['reused']} 张、"
            f"失败 {stats['failed']} 张 → {dest_root.relative_to(BASE)}")
    elif not download and mapping:
        log(f"  图片:按 --no-images 跳过下载,{len(mapping)} 张改为绝对链接")
    return out


def build_bilingual(arxiv_id: str, reg: dict,
                    download_images: bool = True) -> Path | None:
    """为一篇论文生成中英对照 Markdown,返回输出路径。

    步骤:登记条目 → 读缓存 → 翻译缺的段落 → 拼装 Markdown →
    下载图片到 assets/ → 回写缓存与登记表。缓存以"英文原文"为 key,
    所以改输出格式、加纠错词条都不用重新翻译,重跑秒级完成。

    只有成功的译文才写进缓存:失败的段落仅在本次渲染时标 ⚠,重跑会自动
    重试。表格、公式与原文块不进缓存(它们不参与翻译)。
    缓存每 CACHE_FLUSH_EVERY 段增量落盘一次,中途中断不会丢掉已有进度。
    """
    known = {p["id"]: p for p in reg["papers"]}
    if arxiv_id in known:
        entry = known[arxiv_id]
    else:  # 清单外临时指定也支持,顺手登记进去
        log(f"* {arxiv_id} 不在清单中,拉取元数据...")
        # 元数据取不到也照样能生成,标题退化成 id;不写 file 字段,
        # 留给 --all 补全(登记表里没有 file 就说明元数据还没拿到)。
        entry = fetch_metadata(arxiv_id) or {"id": arxiv_id, "title": arxiv_id}
        entry.setdefault("id", arxiv_id)
        entry["category"] = "未分类"
        reg["papers"].append(entry)
        known[arxiv_id] = entry

    out_dir = BILINGUAL_DIR / sanitize(entry.get("category", "未分类"))
    out_dir.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # 缓存按后端分文件:不同后端译文质量不同,混用会让"换后端重译"失效。
    # google 沿用旧的 {id}.json 命名,既有缓存可直接复用、不必重译。
    cache_file = (CACHE_DIR / f"{arxiv_id}.json" if TRANSLATE_BACKEND == "google"
                  else CACHE_DIR / f"{arxiv_id}.{TRANSLATE_BACKEND}.json")
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    # 清掉历史遗留的失败占位:早期版本会把 "⚠ ..." 写进缓存,导致这些段落
    # 永远被当成"已翻译"。删掉即视为未命中,本次会自动重试。
    stale = [k for k, v in cache.items() if isinstance(v, str) and v.startswith(FAIL_MARK)]
    for k in stale:
        del cache[k]
    if stale:
        log(f"  清理 {len(stale)} 条历史失败缓存,本次重试")
    out_file = out_dir / f"{arxiv_id} 中英对照.md"

    # 1) 抓 HTML 并解析(base 是图片基址,两个源的路径格式不同,必须一起带上)
    log(f"* 抓取 {arxiv_id} 的 HTML 版...")
    html, source, base = fetch_paper_html(arxiv_id)
    blocks = parse_blocks(html)
    n_paras = sum(1 for k, _ in blocks if k == "p")
    n_tables = sum(1 for k, _ in blocks if k == "table")
    n_verbatim = sum(1 for k, _ in blocks if k == "verbatim")
    log(f"  来源 {source},共 {len(blocks)} 个区块"
        f"(正文段 {n_paras}、表格 {n_tables}、原文块 {n_verbatim})")

    # 2) 只翻译缓存里没有的段落。失败只记在内存里、不写缓存,否则下次重跑
    #    会因为"缓存命中"而永远跳过它——一次网络抖动就留下永久疤痕。
    failures: dict[str, str] = {}
    todo = [t for kind, t in blocks
            if (kind.startswith("h") or kind == "p") and t not in cache]
    for i, t in enumerate(todo, 1):
        try:
            cache[t] = translate_one(t)
        except RuntimeError as e:
            failures[t] = str(e)
        if i % 10 == 0 or i == len(todo):
            log(f"  翻译进度 {i}/{len(todo)}")
        if i % CACHE_FLUSH_EVERY == 0:
            # 增量落盘:一篇 270 段的论文要跑好几分钟,中途中断(Ctrl-C、
            # 断网、限流卡死)不该把已经翻好的部分全部丢掉。
            write_text_atomic(cache_file, json.dumps(cache, ensure_ascii=False))
        time.sleep(0.4)  # 免费接口,温柔一点

    # 3) 标题单独翻一份,用 "TITLE::" 前缀存在同一个缓存里
    title = entry.get("title") or arxiv_id
    title_key = "TITLE::" + title
    if title_key not in cache:
        try:
            cache[title_key] = translate_one(title)
        except RuntimeError as e:
            failures[title_key] = str(e)
        time.sleep(0.4)

    def zh_of(key: str) -> str:
        """取译文:命中缓存用缓存,否则用本次的失败提示(失败不会写进缓存)。"""
        if key in cache:
            return fix_acronyms(cache[key]).replace("\n", " ")
        err = failures.get(key)
        return f"{FAIL_MARK} 翻译失败:{err}" if err else ""

    # 4) 拼装 Markdown:英文段在上,中文以引用块(>) 缀其下,
    #    章节标题译成斜体——阅读时先裸读英文,再向下扫译文校准
    lines = [f"# {title}", "", f"> **{zh_of(title_key)}**", "",
              f"> 原文: https://arxiv.org/abs/{arxiv_id}", "",
              "> 用法:先裸读英文段,再对照下方引用块中的译文校准。", "",
              "---", ""]
    for kind, text in blocks:
        if kind.startswith("h") and text.strip().lower() == title.strip().lower():
            continue  # 正文首个标题与论文标题重复,跳过
        if kind == "table":
            # 表格按原文保留、不翻译:里面多是数字与模型名,逐格机翻既容易
            # 破坏表结构,对阅读也没什么帮助。保留数据本身才是重点。
            lines += ["【表格】", "", text, ""]
            continue
        if kind == "verbatim":
            # 单列表格(prompt 模板/代码清单),同样原样保留不翻译。
            lines += ["【原文块】", "", text, ""]
            continue
        zh = SECTION_ZH.get(text.strip()) or zh_of(text)
        if kind.startswith("h"):
            # kind 形如 "h3",级别来自 heading_level(),不再是清一色 ##
            lines += [f"{'#' * int(kind[1:])} {text}", f"*{zh}*" if zh else "", ""]
        elif kind == "formula":
            lines += [f"$$\n{text}\n$$", ""]
        elif kind == "image":
            # 只留原始相对路径,绝对化与本地化统一交给 localize_images
            src, _, alt = text.partition("\t")
            lines += [f"![{alt}]({src})", ""]
        else:
            lines += [text, "", f"> {zh}" if zh else "", ""]
    # 5) 图片落地:把正文里的远程图片链接下载到 assets/,换成相对路径引用
    lines = localize_images(lines, arxiv_id, base, download=download_images)
    write_text_atomic(out_file, "\n".join(lines))

    # 5) 回写:缓存落盘(断点续传的依据),登记表记录产出路径(--list 显示 ◈)
    write_text_atomic(cache_file, json.dumps(cache, ensure_ascii=False))
    entry["bilingual"] = str(out_file.relative_to(BASE))
    save_registry(reg)
    log(f"✓ 已生成 {out_file.relative_to(BASE)}")
    if failures:
        log(f"  ! {len(failures)} 段翻译失败,已跳过且未写入缓存(重跑会自动重试)")
    return out_file


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
def main() -> int:
    # Windows 控制台默认 GBK,打印 ✓/⚠ 等字符会崩,强制切到 UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # add_help 保持默认的 True:之前设成 False 又没别的参数占用 -h,
    # 结果 --help/-h 一律报 "unrecognized arguments",帮助只能靠不带参数触发。
    ap = argparse.ArgumentParser(
        description="arXiv 论文下载脚手架:下载 PDF、生成中英对照阅读材料",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python fetch_papers.py --all                      下载清单中所有未落盘论文\n"
               "  python fetch_papers.py 2501.12948 -c 推理前沿      添加并下载一篇\n"
               "  python fetch_papers.py --bilingual 2501.12948     生成中英对照材料\n"
               "  python fetch_papers.py --list                     查看清单与状态\n")
    ap.add_argument("papers", nargs="*", help="arXiv id 或 arxiv.org 链接")
    ap.add_argument("-c", "--category", default=None, help="新增论文的分类(目录名)")
    ap.add_argument("-a", "--all", action="store_true", help="下载清单中所有未落盘论文")
    ap.add_argument("-f", "--force", action="store_true", help="已存在也重新下载")
    ap.add_argument("-l", "--list", action="store_true", help="列出清单")
    ap.add_argument("-p", "--proxy", default=None,
                    help="HTTP 代理,如 http://127.0.0.1:7897(也可用环境变量 HTTPS_PROXY)")
    ap.add_argument("-b", "--bilingual", default=None, metavar="ID|all",
                    help="为指定论文(或 all=全部)生成中英对照阅读材料")
    ap.add_argument("--no-images", action="store_true",
                    help="不下载插图,只把图片链接补全成 arXiv 绝对地址(离线可用)")
    ap.add_argument("-t", "--translator", default=None, choices=["google", "openai"],
                    help="翻译后端:google=免费网页接口(默认) / "
                         "openai=OpenAI 兼容接口")
    ap.add_argument("--translate-base-url", default=None,
                    help="openai 后端的 API 地址,如 https://api.deepseek.com/v1")
    ap.add_argument("--translate-model", default=None,
                    help="openai 后端的模型名,如 deepseek-chat")
    ap.add_argument("--translate-api-key", default=None,
                    help="openai 后端的 API Key(建议改用环境变量 TRANSLATE_API_KEY)")
    args = ap.parse_args()

    global PROXY, TRANSLATE_BACKEND, OPENAI_BASE_URL, OPENAI_MODEL, TRANSLATE_API_KEY
    settings = Settings.from_values(
        proxy=args.proxy,
        translator=args.translator,
        base_url=args.translate_base_url,
        model=args.translate_model,
        api_key=args.translate_api_key,
    )
    PROXY = settings.proxy
    TRANSLATE_BACKEND = settings.translate_backend
    OPENAI_BASE_URL = settings.openai_base_url
    OPENAI_MODEL = settings.openai_model
    TRANSLATE_API_KEY = settings.translate_api_key

    reg = load_registry()
    known = {p["id"]: p for p in reg["papers"]}

    # ---- 模式一:--list,本地操作,不联网 ----
    if args.list:
        for p in reg["papers"]:
            cat = p.get("category", "未分类")
            if "file" not in p:      # 元数据还没补全的条目
                log(f" [  ] {cat:<10} {p['id']} (待补全元数据)")
                continue
            path = OUTDIR / sanitize(cat) / p["file"]
            mark = "✓" if path.exists() else " "
            # ◈ 也查一次磁盘:只看 registry 字段的话,删掉 md 之后仍会显示已生成
            bi = "◈" if (p.get("bilingual")
                         and (BASE / Path(p["bilingual"])).exists()) else " "
            log(f" [{mark}{bi}] {cat:<10} {p['file']}")
        log(f"\n共 {len(reg['papers'])} 篇(◈ = 已生成中英对照)")
        return 0

    # ---- 模式二:--bilingual,生成中英对照材料 ----
    if args.bilingual:
        if args.bilingual.strip().lower() == "all":
            ids = [p["id"] for p in reg["papers"]]
        else:
            ids = [parse_arxiv_id(args.bilingual) or args.bilingual.strip()]
        for i, pid in enumerate(ids, 1):
            log(f"[{i}/{len(ids)}] 生成中英对照 {pid}")
            try:
                build_bilingual(pid, reg, download_images=not args.no_images)
            except Exception as e:  # 单篇失败不拖垮整批
                log(f"  ✗ 失败: {e}")
            if i < len(ids):
                time.sleep(3)
        return 0

    # ---- 模式三:--all,批量补齐 PDF ----
    if args.all:
        if not reg["papers"]:
            log("papers.json 为空,先用 `python fetch_papers.py <id>` 添加论文。")
            return 0
        ok = 0
        dirty = False
        total = len(reg["papers"])
        for i, p in enumerate(reg["papers"], 1):
            if "file" not in p:  # 清单里只登记了 id,先补全元数据
                log(f"[{i}/{total}] {p['id']} (拉取元数据...)")
                if not ensure_metadata(p):
                    log(f"  ! 元数据未取到,本条跳过(下次 --all 会重试)")
                    time.sleep(3)
                    continue
                dirty = True
                time.sleep(3)
            else:
                log(f"[{i}/{total}] {p['id']}")
            if download_entry(p, force=args.force) != "failed":
                ok += 1
            time.sleep(3)  # arXiv 限流:请求间隔 ≥3s
        if dirty:
            save_registry(reg)
        log(f"\n完成:{ok}/{total} 篇可用,存于 {OUTDIR}")
        return 0

    # ---- 模式四:位置参数,添加并下载指定论文 ----
    if not args.papers:
        ap.print_help()
        return 0

    added, ok = 0, 0
    for i, text in enumerate(args.papers):
        entry = resolve_entry(text, args.category)
        if entry is None:
            continue
        if entry["id"] not in known:  # 已登记的只下载,不重复入表
            reg["papers"].append(entry)
            known[entry["id"]] = entry
            added += 1
        log(f"[{i + 1}/{len(args.papers)}] {entry['id']} - "
            f"{entry.get('title', '(元数据待补全)')[:60]}")
        if "file" not in entry:
            continue  # 元数据没拿到,下次 --all 再补全并下载
        if download_entry(entry, force=args.force) != "failed":
            ok += 1
        if i < len(args.papers) - 1:
            time.sleep(3)

    save_registry(reg)
    log(f"\n新增登记 {added} 篇,本次成功 {ok} 篇,存于 {OUTDIR}")
    return 0


# 兼容再导出:实现已移入 paperkit.domain,这里保留原有模块级名字,
# 使 fetch_papers.py 兼容壳与现有测试的 fp.xxx 调用继续可用。
# 其中 PaperHTMLParser / heading_level / render_* 本模块已不再内部使用,
# 仅作为对外表面保留;待 P3 编排逻辑移入 services 后,core.py 整体删除。


if __name__ == "__main__":
    sys.exit(main())
