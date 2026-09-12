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

  python fetch_papers.py --bilingual <id|all>
      生成中英对照阅读材料到 papers/双语/

  python fetch_papers.py --list
      查看清单及下载状态([✓]=PDF已下载 [◈]=对照材料已生成)

说明:
  * --force 可强制重新下载;--proxy 指定 HTTP 代理(直连 arXiv 常被阻断)。
  * 文件名自动取 arXiv 元数据,格式: 年份 - 第一作者 et al. - 标题 [id].pdf
  * 对 arXiv 的请求间隔 3 秒,遵守其限流要求。
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

# ---------------------------------------------------------------------------
# 全局路径与常量(全部相对脚本所在目录,挪动整个文件夹也不受影响)
# ---------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent       # 本脚本所在目录
REGISTRY = BASE / "papers.json"              # 论文登记表
OUTDIR = BASE / "papers"                     # PDF 与对照材料的根目录
ATOM = "{http://www.w3.org/2005/Atom}"       # arXiv API 返回的 XML 命名空间前缀

UA = {"User-Agent": "paper-fetcher/0.1 (personal study use)"}
PROXY = None  # 形如 http://127.0.0.1:7897,由 --proxy 或环境变量 HTTPS_PROXY 设置


# ---------------------------------------------------------------------------
# 基础工具:日志、HTTP(带代理)
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    """flush=True 让输出立刻上屏——批量任务里能实时看到进度。"""
    print(msg, flush=True)


def http_get(url: str, timeout: int = 60) -> bytes:
    """发 GET 请求返回响应体;设置了 PROXY 时所有流量都走代理。

    Python 标准库默认不理会代码里设的代理环境变量语义,这里显式构建
    ProxyHandler,保证 --proxy 参数对每个请求都生效。
    """
    req = urllib.request.Request(url, headers=UA)
    if PROXY:
        handler = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
        opener = urllib.request.build_opener(handler)
        with opener.open(req, timeout=timeout) as resp:
            return resp.read()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


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
    REGISTRY.write_text(
        json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# arXiv 元数据
# ---------------------------------------------------------------------------
def parse_arxiv_id(text: str) -> str | None:
    """从各种输入形态提取 arXiv id(如 '2501.12948'),认不出返回 None。

    兼容: 裸 id '2501.12948v2' / abs 链接 / pdf 链接。
    两个正则的区别:fullmatch 要求整串完全匹配(裸 id),search 允许嵌在 URL 里。
    """
    text = text.strip()
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})(v\d+)?", text, re.I)
    if m:
        return m.group(1)
    m = re.fullmatch(r"([0-9]{4}\.[0-9]{4,5})(v\d+)?", text)
    if m:
        return m.group(1)
    return None


def fetch_metadata(arxiv_id: str) -> dict:
    """通过 arXiv Atom API 拿标题/作者/年份。失败时返回最小占位信息。

    API 一次可查多篇,这里简单起见逐篇查。网络失败不应阻塞整批下载,
    所以捕获所有异常、降级为占位(标题=id),后续 --all 还能重试补全。
    """
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        root = ET.fromstring(http_get(url))
        entry = root.find(f"{ATOM}entry")
        if entry is None:
            raise ValueError("entry not found")
        # 标题里的换行/多空格压成一个空格,否则文件名会断裂
        title = re.sub(r"\s+", " ", entry.findtext(f"{ATOM}title", "").strip())
        authors = [
            a.findtext(f"{ATOM}name", "").strip()
            for a in entry.findall(f"{ATOM}author")
        ]
        published = entry.findtext(f"{ATOM}published", "")[:4]  # '2025-01-...' -> '2025'
        return {"title": title, "authors": authors, "year": published or "????", "id": arxiv_id}
    except Exception as e:
        log(f"  ! 元数据获取失败({e}),使用占位文件名")
        return {"title": arxiv_id, "authors": [], "year": "????", "id": arxiv_id}


# ---------------------------------------------------------------------------
# 文件名生成
# ---------------------------------------------------------------------------
def sanitize(name: str) -> str:
    """把任意字符串变成合法的 Windows 文件/目录名。

    三步:NFKC 规范化(全角→半角等)→ 删非法字符 → 压空白、去首尾点。
    """
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:200]


def make_filename(meta: dict) -> str:
    """生成 '年份 - 第一作者 et al. - 标题 [id].pdf'。

    先 sanitize 再截断到 180 字符、最后拼 .pdf——顺序不能反,
    否则超长标题会把 .pdf 后缀截掉(早期版本的 bug)。
    """
    authors = meta.get("authors") or []
    if authors:
        first = authors[0].split()[-1]           # 取第一作者的姓(最后一个词)
        etal = " et al." if len(authors) > 1 else ""
    else:
        first, etal = "Unknown", ""
    base = sanitize(f"{meta['year']} - {first}{etal} - {meta['title']} [{meta['id']}]")
    return base[:180] + ".pdf"


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
    """把命令行输入(id 或 URL)解析成一条完整的登记条目。"""
    arxiv_id = parse_arxiv_id(text)
    if not arxiv_id:
        log(f"! 无法识别: {text} (需要 arXiv id 或 arxiv.org 链接)")
        return None
    log(f"* 拉取元数据 {arxiv_id} ...")
    meta = fetch_metadata(arxiv_id)
    cat = category or "未分类"
    fname = make_filename(meta)
    return {**meta, "category": cat, "file": fname}


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
# Google 翻译的免费网页接口(Chrome 划词词典用的通道),GET 请求,q= 后接
# URL 编码的英文,返回 JSON。相比正式 Cloud API 免认证,但有频率限制。
TRANSLATE_URL = ("https://clients5.google.com/translate_a/t"
                 "?client=dict-chrome-ex&sl=en&tl=zh-CN&q=")
MIN_PARA_CHARS = 40  # 短于此的段落视为导航/噪声,丢弃

# 常见章节名固定译法,避免逐词机翻产生"抽象的"这类笑话
SECTION_ZH = {
    "Abstract": "摘要", "Introduction": "引言", "Conclusion": "结论",
    "Conclusions": "结论", "Discussion": "讨论", "Acknowledgments": "致谢",
    "Acknowledgements": "致谢", "References": "参考文献", "Appendix": "附录",
    "Related Work": "相关工作", "Conclusion and Future Work": "结论与展望",
    "Experiments": "实验", "Experimental Setup": "实验设置",
    "Limitations": "局限性", "Ethics Statement": "伦理声明",
    "Broader Impact": "更广泛的影响", "Background": "背景",
}

# 机翻缩写纠错:Google 会把 LLM(s) 译成"法学硕士"等,输出时替换。
# 注意必须在"写出 Markdown 时"替换而非缓存时——这样以后扩充词条,
# 老缓存不用重新翻译,重跑一遍就能全部修正。
ACRONYM_FIX = {
    "法学硕士们": "大语言模型", "法学硕士": "大语言模型",
    "大型语言模型(大语言模型)": "大语言模型",
    "提示工程学": "提示工程", "提示词工程学": "提示工程",
}


def fix_acronyms(zh: str) -> str:
    """对译文做缩写纠错(顺序遍历替换表)。"""
    for bad, good in ACRONYM_FIX.items():
        zh = zh.replace(bad, good)
    return zh


class PaperHTMLParser(HTMLParser):
    """从 arXiv/ar5iv 的 HTML 中抽取标题与正文段落。

    这是事件驱动的流式解析:HTMLParser 边扫标签边回调,我们不建 DOM 树。
    状态用三个实例变量维护:
      _blocks  结果列表,("h"|"p", 文本)  h=章节标题 p=正文/图注
      _skip    正在跳过的标签栈(遇到 </x> 弹出),用于忽略 script/svg 等
      _buf     当前正在累积的文本;进入 <p>/<h*> 时置空开始收集,
               遇到结束标签时 _flush() 收尾——这样标签内再嵌 <span>、
               <b> 等行内标签也不受影响,文本自然接在一起。

    三类特殊处理:
      - <math> 用其 alttext 以 $...$ 形式内联,避免公式变成乱码
      - 跳过 script/style/svg 与参考文献(ltx_bibliograph)
      - 图注(figcaption)加【图注】前缀保留为独立段落
    """

    def __init__(self):
        # convert_charrefs=True: &amp; 这类 HTML 实体自动解码成普通字符
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []
        self._skip: list[str] = []
        self._buf: str | None = None
        self._kind = "p"
        self._formula_buf: str | None = None

    def _skip_this(self, tag: str, attrs: dict) -> bool:
        """判断某标签子树是否整体不要(脚本/样式/参考文献)。"""
        if tag in ("script", "style", "svg", "noscript"):
            return True
        if "ltx_bibliograph" in attrs.get("class", ""):
            return True
        return False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "img":
            src = (a.get("src") or a.get("data-src") or
                   a.get("data-lazy-src") or a.get("data-original"))
            if not src and a.get("srcset"):
                src = a["srcset"].split(",")[0].strip().split(" ")[0]
            if src:
                self.blocks.append(("image", f"{src}\t{a.get('alt', '').strip()}"))
            return
        if self._skip:  # 已在跳过中:嵌套的可跳过标签入栈,其余无视
            if self._skip_this(tag, a) or tag == "math":
                self._skip.append(tag)
            return
        if self._skip_this(tag, a):
            self._skip.append(tag)
            return
        if tag == "math":  # 公式以内联 LaTeX 呈现
            alt = (a.get("alttext") or "").replace("\n", " ")
            if alt and self._buf is not None:
                self._buf += f" ${alt}$ "
            elif alt:
                self.blocks.append(("formula", alt.strip()))
            self._skip.append(tag)  # <math> 的渲染内容不要,只要 alttext
            return
        if tag == "img":
            src = a.get("src") or a.get("data-src")
            if src:
                alt = a.get("alt", "").strip()
                self.blocks.append(("image", f"{src}\t{alt}"))
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "figcaption"):
            if self._buf is not None:  # 上一段没闭合就开了新段:先结算
                self._flush()
            self._buf = ""
            self._kind = "h" if tag.startswith("h") else "p"
            if tag == "figcaption":
                self._kind = "cap"

    def handle_endtag(self, tag):
        if self._skip:  # 只有栈顶标签的 </x> 才弹栈,防止嵌套误配
            if tag == self._skip[-1]:
                self._skip.pop()
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "figcaption"):
            if self._buf is not None:
                self._flush()

    def handle_data(self, data):
        """纯文本节点:不在跳过区且正在收集段落时,追加进缓冲。"""
        if self._skip or self._buf is None:
            return
        self._buf += data

    def _flush(self):
        """结束一个区块:压缩空白、按类型过滤噪声后存入结果。"""
        text = re.sub(r"\s+", " ", self._buf or "").strip()
        kind, self._buf = self._kind, None
        if kind == "h":
            if text:
                self.blocks.append(("h", text))
        elif kind == "cap":
            if len(text) >= 20:  # 太短的图注多为 "(a)" 之类的编号
                self.blocks.append(("p", "【图注】" + text))
        else:
            if len(text) >= MIN_PARA_CHARS:
                self.blocks.append(("p", text))


def fetch_paper_html(arxiv_id: str) -> tuple[str, str]:
    """抓取论文 HTML 版,优先 arXiv 原生,失败退回 ar5iv。返回 (html, 来源)。

    arXiv 官方 HTML 只有 2024 年初以后的论文;更早的由 ar5iv(公益项目,
    同样是 LaTeXML 渲染)兜底。两个源的 HTML 结构相同,后面解析无差别。
    """
    sources = [
        (f"https://arxiv.org/html/{arxiv_id}", "arxiv"),
        (f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}", "ar5iv"),
    ]
    last_err = None
    for url, name in sources:
        try:
            html = http_get(url, timeout=90).decode("utf-8", errors="replace")
            if "<p" in html or "ltx_" in html:  # 粗验:页面确实有正文
                return html, name
            last_err = f"{name}: 页面无正文"
        except Exception as e:
            last_err = f"{name}: {e}"
    raise RuntimeError(f"拿不到 HTML 版({last_err});纯扫描版 PDF 无法自动提取")


def parse_blocks(html: str) -> list[tuple[str, str]]:
    """HTML → 区块序列。

    先做字符串级裁剪:只保留 <div class="ltx_page_main">(论文正文容器)
    到页脚之间的部分,把 ar5iv/arxiv 页面的导航按钮、页脚等噪声整个
    切掉——这比在解析器里逐个过滤省事得多。
    """
    start = html.find("ltx_page_main")
    if start != -1:
        html = html[start:]
    for stop in ("ltx_page_footer", "</article>", "</body>"):
        end = html.find(stop)
        if end != -1:
            html = html[:end]
            break
    p = PaperHTMLParser()
    p.feed(html)
    # Some arXiv HTML variants use malformed/lazy-loaded image markup that
    # HTMLParser may skip. Recover image sources from the same main-content HTML.
    if not any(kind == "image" for kind, _ in p.blocks):
        for match in re.finditer(r"<img\b([^>]*)>", html, re.I | re.S):
            attrs = dict(re.findall(r'''([\w:-]+)\s*=\s*["']([^"']*)["']''', match.group(1)))
            src = (attrs.get("src") or attrs.get("data-src") or
                   attrs.get("data-lazy-src") or attrs.get("data-original"))
            if not src and attrs.get("srcset"):
                src = attrs["srcset"].split(",")[0].strip().split(" ")[0]
            if src:
                p.blocks.append(("image", f"{src}\t{attrs.get('alt', '').strip()}"))
    return p.blocks


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


def translate_one(text: str) -> str:
    """翻译一段英文;接口重试 3 次(退避 2/4/6 秒),全部失败则抛异常。

    接口返回格式有两种形态(列表或字典),都做了兼容。长段先分块,
    各块分别翻译后按顺序拼接——所以译文的句间衔接可能生硬,这是
    免费 Sentence-level MT 的固有局限。
    """
    # Protect LaTeX from the translation service, which may otherwise remove
    # commands or rewrite symbols. Restore the exact source after translation.
    formulas = []
    def protect(match):
        formulas.append(match.group(0))
        return f" __FORMULA_{len(formulas) - 1}__ "
    protected = re.sub(r"\$\$.*?\$\$|\$[^$\n]+\$", protect, text, flags=re.S)
    last_err = None
    for attempt in range(3):
        try:
            out = []
            for piece in _split_for_translate(protected):
                url = TRANSLATE_URL + urllib.parse.quote(piece)
                data = json.loads(http_get(url, timeout=30).decode("utf-8"))
                if isinstance(data, list):
                    out.append("".join(
                        x if isinstance(x, str) else x[0] for x in data
                    ))
                elif isinstance(data, dict):
                    out.append(data.get("sentences", [{}])[0].get("trans", ""))
            translated = "".join(out).strip()
            for i, formula in enumerate(formulas):
                translated = translated.replace(f"__FORMULA_{i}__", formula)
            return translated
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"翻译失败: {last_err}")


def build_bilingual(arxiv_id: str, reg: dict) -> Path | None:
    """为一篇论文生成中英对照 Markdown,返回输出路径。

    五步:登记条目 → 读缓存 → 翻译缺的段落 → 拼装 Markdown → 回写
    缓存与登记表。缓存以"英文原文"为 key,所以改输出格式、加纠错词条
    都不用重新翻译,重跑秒级完成。
    """
    known = {p["id"]: p for p in reg["papers"]}
    if arxiv_id in known:
        entry = known[arxiv_id]
    else:  # 清单外临时指定也支持,顺手登记进去
        log(f"* {arxiv_id} 不在清单中,拉取元数据...")
        entry = fetch_metadata(arxiv_id)
        entry["category"] = "未分类"
        reg["papers"].append(entry)
        known[arxiv_id] = entry

    out_dir = BILINGUAL_DIR / sanitize(entry.get("category", "未分类"))
    out_dir.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{arxiv_id}.json"
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    out_file = out_dir / f"{arxiv_id} 中英对照.md"

    # 1) 抓 HTML 并解析
    log(f"* 抓取 {arxiv_id} 的 HTML 版...")
    html, source = fetch_paper_html(arxiv_id)
    blocks = parse_blocks(html)
    n_paras = sum(1 for k, _ in blocks if k != "h")
    log(f"  来源 {source},共 {len(blocks)} 个区块(正文段 {n_paras})")

    # 2) 只翻译缓存里没有的段落;失败的段落记为 ⚠ 而不是中断整篇
    todo = [t for kind, t in blocks if kind in ("h", "p") and t not in cache]
    for i, t in enumerate(todo, 1):
        try:
            cache[t] = translate_one(t)
        except RuntimeError as e:
            cache[t] = "⚠ " + str(e)
        if i % 10 == 0 or i == len(todo):
            log(f"  翻译进度 {i}/{len(todo)}")
        time.sleep(0.4)  # 免费接口,温柔一点

    # 3) 标题单独翻一份,用 "TITLE::" 前缀存在同一个缓存里
    title = entry.get("title") or arxiv_id
    title_key = "TITLE::" + title
    if title_key not in cache:
        try:
            cache[title_key] = translate_one(title)
        except RuntimeError as e:
            cache[title_key] = "⚠ " + str(e)
        time.sleep(0.4)

    # 4) 拼装 Markdown:英文段在上,中文以引用块(>) 缀其下,
    #    章节标题译成斜体——阅读时先裸读英文,再向下扫译文校准
    lines = [f"# {title}", "", f"> **{fix_acronyms(cache[title_key])}**", "",
              f"> 原文: https://arxiv.org/abs/{arxiv_id}", "",
              "> 用法:先裸读英文段,再对照斜体译文校对;⭐ 标记值得收进 glossary 的表达。", "",
              "---", ""]
    for kind, text in blocks:
        if kind == "h" and text.strip().lower() == title.strip().lower():
            continue  # 正文首个标题与 H1 重复,跳过
        zh = SECTION_ZH.get(text.strip()) or fix_acronyms(cache.get(text, "")).replace("\n", " ")
        if kind == "h":
            lines += [f"## {text}", f"*{zh}*" if zh else "", ""]
        elif kind == "formula":
            lines += [f"$$\n{text}\n$$", ""]
        elif kind == "image":
            src, _, alt = text.partition("\t")
            src = urllib.parse.urljoin(f"https://arxiv.org/html/{arxiv_id}/", src)
            lines += [f"![{alt}]({src})", ""]
        else:
            lines += [text, "", f"> {zh}" if zh else "", ""]
    out_file.write_text("\n".join(lines), encoding="utf-8")

    # 5) 回写:缓存落盘(断点续传的依据),登记表记录产出路径(--list 显示 ◈)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    entry["bilingual"] = str(out_file.relative_to(BASE))
    save_registry(reg)
    log(f"✓ 已生成 {out_file.relative_to(BASE)}")
    return out_file


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
def main() -> int:
    # Windows 控制台默认 GBK,打印 ✓/⚠ 等字符会崩,强制切到 UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(add_help=False, description="arXiv 论文下载脚手架")
    ap.add_argument("papers", nargs="*", help="arXiv id 或 arxiv.org 链接")
    ap.add_argument("-c", "--category", default=None, help="新增论文的分类(目录名)")
    ap.add_argument("-a", "--all", action="store_true", help="下载清单中所有未落盘论文")
    ap.add_argument("-f", "--force", action="store_true", help="已存在也重新下载")
    ap.add_argument("-l", "--list", action="store_true", help="列出清单")
    ap.add_argument("-p", "--proxy", default=None,
                    help="HTTP 代理,如 http://127.0.0.1:7897(也可用环境变量 HTTPS_PROXY)")
    ap.add_argument("-b", "--bilingual", default=None, metavar="ID|all",
                    help="为指定论文(或 all=全部)生成中英对照阅读材料")
    args = ap.parse_args()

    global PROXY
    PROXY = args.proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

    reg = load_registry()
    known = {p["id"]: p for p in reg["papers"]}

    # ---- 模式一:--list,本地操作,不联网 ----
    if args.list:
        for p in reg["papers"]:
            path = OUTDIR / sanitize(p["category"]) / p["file"]
            mark = "✓" if path.exists() else " "
            bi = "◈" if p.get("bilingual") else " "
            log(f" [{mark}{bi}] {p['category']:<10} {p['file']}")
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
                build_bilingual(pid, reg)
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
        for i, p in enumerate(reg["papers"], 1):
            if "file" not in p:  # 清单里只登记了 id,先补全元数据
                log(f"[{i}/{len(reg['papers'])}] {p['id']} (拉取元数据...)")
                meta = fetch_metadata(p["id"])
                p.update(meta)
                p["category"] = p.get("category", "未分类")
                p["file"] = make_filename(p)
                dirty = True
                time.sleep(3)
            else:
                log(f"[{i}/{len(reg['papers'])}] {p['id']}")
            if download_entry(p, force=args.force) != "failed":
                ok += 1
            time.sleep(3)  # arXiv 限流:请求间隔 ≥3s
        if dirty:
            save_registry(reg)
        log(f"\n完成:{ok}/{len(reg['papers'])} 篇可用,存于 {OUTDIR}")
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
        log(f"[{i + 1}/{len(args.papers)}] {entry['id']} - {entry['title'][:60]}")
        if download_entry(entry, force=args.force) != "failed":
            ok += 1
        if i < len(args.papers) - 1:
            time.sleep(3)

    save_registry(reg)
    log(f"\n新增登记 {added} 篇,本次成功 {ok} 篇,存于 {OUTDIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
