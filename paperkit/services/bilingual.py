"""生成中英对照阅读材料——本项目的核心用例。

流程:查是否已生成(未 force 则跳过)→ 登记条目 → 读缓存 → 只翻译缺的段落 →
拼装 Markdown → 下载插图 → 回写缓存与登记表。缓存以「英文原文」为 key,所以
改输出格式、加纠错词条都不用重新翻译,重跑秒级完成。

设计上刻意把两件事做成可注入的:
  * translator —— 传一个满足 Translator 协议的假实现,就能零网络跑完整条链路
  * settings   —— 传 Settings(base_dir=tmp),产物全部落在临时目录,不污染真实数据
重构前这两件事都要靠 mock.patch 改模块级全局才能做到。
"""

import time
from pathlib import Path

from ..config import Settings
from ..domain import SECTION_ZH, fix_acronyms, parse_arxiv_id, parse_blocks, sanitize
from ..errors import TranslateError
from ..infra.arxiv_api import fetch_metadata, fetch_paper_html
from ..infra.cache import TranslationCache
from ..infra.logging import log
from ..infra.storage import RegistryStore, write_text_atomic
from ..infra.translate import Translator, translate_one
from .images import INLINE_PREFIX, localize_images


def target_ids(target: str, reg: dict) -> list[str]:
    """把 -b 的参数展开成 id 列表:'all' → 全清单,否则解析单个 id/链接。

    放在 services 而不是 cli,是为了让 cli 只依赖 services 一层。
    """
    if target.strip().lower() == "all":
        return [p["id"] for p in reg["papers"]]
    return [parse_arxiv_id(target) or target.strip()]


def _resolve_entry(arxiv_id: str, reg: dict, settings: Settings) -> dict:
    """在登记表里找到条目;没有就顺手登记一条(元数据拿不到也照样能生成)。"""
    known = {p["id"]: p for p in reg["papers"]}
    if arxiv_id in known:
        return known[arxiv_id]
    log(f"* {arxiv_id} 不在清单中,拉取元数据...")
    # 元数据取不到也照样能生成,标题退化成 id;不写 file 字段,
    # 留给 --all 补全(登记表里没有 file 就说明元数据还没拿到)。
    entry = fetch_metadata(arxiv_id, settings) or {"id": arxiv_id,
                                                  "title": arxiv_id}
    entry.setdefault("id", arxiv_id)
    entry["category"] = "未分类"
    reg["papers"].append(entry)
    return entry


def is_generated(entry: dict, settings: Settings | None = None) -> bool:
    """该条目是否已生成过中英对照材料。

    两个条件都要满足:登记表里有 bilingual 字段,**且**文件确实在磁盘上。
    只看字段的话,手工删掉 md 之后仍会被判为已完成;--list 的 ◈ 用的是
    同一口径(见 services/listing.py)。
    """
    s = settings or Settings()
    rel = entry.get("bilingual")
    return bool(rel) and (s.base_dir / Path(rel)).exists()


def build_bilingual(arxiv_id: str, reg: dict,
                    settings: Settings | None = None,
                    translator: Translator | None = None,
                    download_images: bool = True,
                    force: bool = False) -> Path | None:
    """为一篇论文生成中英对照 Markdown,返回输出路径。

    force=False 时,已生成过的直接跳过并返回原路径(不联网、不改登记表)。
    这一步很要紧:抓 HTML 排在「哪些段落需要翻译」的判断之前,所以即使
    译文全部命中缓存,每篇仍要发一次网络请求;库越大浪费越明显,中断后
    重跑 `--bilingual all` 也无法真正「接着跑」。
    """
    s = settings or Settings()
    entry = _resolve_entry(arxiv_id, reg, s)

    out_dir = s.bilingual_dir / sanitize(entry.get("category", "未分类"))
    out_file = out_dir / f"{arxiv_id} 中英对照.md"
    if not force and is_generated(entry, s):
        log(f"= 跳过已生成 {out_file.relative_to(s.base_dir)}(--force 可重建)")
        return out_file          # 刻意不建目录:跳过就什么都不该动

    out_dir.mkdir(parents=True, exist_ok=True)
    s.cache_dir.mkdir(parents=True, exist_ok=True)

    cache = TranslationCache(s.cache_file(arxiv_id),
                             flush_every=s.cache_flush_every,
                             fail_mark=s.fail_mark).load()
    if cache.pruned:
        log(f"  清理 {cache.pruned} 条历史失败缓存,本次重试")

    # 1) 抓 HTML 并解析(base 是图片基址,两个源的路径格式不同,必须一起带上)
    log(f"* 抓取 {arxiv_id} 的 HTML 版...")
    html, source, base = fetch_paper_html(arxiv_id, s)
    blocks = parse_blocks(html)
    n_paras = sum(1 for k, _ in blocks if k == "p")
    n_tables = sum(1 for k, _ in blocks if k == "table")
    n_verbatim = sum(1 for k, _ in blocks if k == "verbatim")
    n_images = sum(1 for k, _ in blocks if k in ("image", "svg"))
    log(f"  来源 {source},共 {len(blocks)} 个区块"
        f"(正文段 {n_paras}、表格 {n_tables}、原文块 {n_verbatim}、"
        f"插图 {n_images})")

    # 2) 只翻译缓存里没有的段落。失败只记在内存里、不写缓存,否则下次重跑
    #    会因为"缓存命中"而永远跳过它——一次网络抖动就留下永久疤痕。
    failures: dict[str, str] = {}
    todo = [t for kind, t in blocks
            if (kind.startswith("h") or kind == "p") and t not in cache]
    for i, t in enumerate(todo, 1):
        try:
            cache.put(t, translate_one(t, s, translator))
        except TranslateError as e:
            failures[t] = str(e)
        if i % 10 == 0 or i == len(todo):
            log(f"  翻译进度 {i}/{len(todo)}")
        time.sleep(s.request_delay)  # 免费接口,温柔一点

    # 3) 标题单独翻一份,用 "TITLE::" 前缀存在同一个缓存里
    title = entry.get("title") or arxiv_id
    title_key = "TITLE::" + title
    if title_key not in cache:
        try:
            cache.put(title_key, translate_one(title, s, translator))
        except TranslateError as e:
            failures[title_key] = str(e)
        time.sleep(s.request_delay)

    def zh_of(key: str) -> str:
        """取译文:命中缓存用缓存,否则用本次的失败提示(失败不会写进缓存)。"""
        if key in cache:
            return fix_acronyms(cache[key]).replace("\n", " ")
        err = failures.get(key)
        return f"{s.fail_mark} 翻译失败:{err}" if err else ""

    # 4) 拼装 Markdown:英文段在上,中文以引用块(>) 缀其下,
    #    章节标题译成斜体——阅读时先裸读英文,再向下扫译文校准
    lines = [f"# {title}", "", f"> **{zh_of(title_key)}**", "",
             f"> 原文: https://arxiv.org/abs/{arxiv_id}", "",
             "> 用法:先裸读英文段,再对照下方引用块中的译文校准。", "",
             "---", ""]
    # 内联插图的标记没法塞进 Markdown 链接,先收集起来,第 5 步落盘时取用
    inline_svgs: dict[str, str] = {}
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
        elif kind == "svg":
            # 内联插图:没有 URL,把标记登记下来,链接用伪协议占位,
            # 第 5 步由 localize_images 写成 assets/<id>/inline/<名字>.svg
            name, _, markup = text.partition("\t")
            key = f"{INLINE_PREFIX}{name}"
            inline_svgs[key] = markup
            lines += [f"![{name}]({key})", ""]
        else:
            lines += [text, "", f"> {zh}" if zh else "", ""]

    # 5) 图片落地:把正文里的远程图片链接下载到 assets/,换成相对路径引用
    lines = localize_images(lines, arxiv_id, base, s, download=download_images,
                            inline_svgs=inline_svgs)
    write_text_atomic(out_file, "\n".join(lines))

    # 6) 回写:缓存落盘(断点续传的依据),登记表记录产出路径(--list 显示 ◈)
    cache.flush()
    entry["bilingual"] = str(out_file.relative_to(s.base_dir))
    RegistryStore(s.registry_path).save(reg)
    log(f"✓ 已生成 {out_file.relative_to(s.base_dir)}")
    if failures:
        log(f"  ! {len(failures)} 段翻译失败,已跳过且未写入缓存(重跑会自动重试)")
    return out_file
