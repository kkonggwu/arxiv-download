"""命令行入口:解析参数 → 组装 Settings → 调用 services → 决定退出码。

这是**唯一**允许碰 sys.argv / sys.stdout / 环境变量的地方。所有下游模块
都通过参数接收配置,因此可以在测试里完整地驱动一遍而不触碰真实环境。

退出码约定:
    0  全部成功(或没有需要处理的内容)
    1  全部失败
    2  部分失败(批量模式下单篇失败不拖垮整批)
    3  参数或配置错误
"""

import argparse
import sys
import time
from pathlib import Path

from ..config import Settings
from ..errors import PaperKitError
from ..infra.logging import log
from ..services import (
    build_bilingual,
    download_entry,
    ensure_metadata,
    is_generated,
    link_wiki,
    load_registry,
    paper_rows,
    resolve_entry,
    save_registry,
    summary_line,
    target_ids,
)

EPILOG = """示例:
  papers --all                       下载清单中所有未落盘论文
  papers 2501.12948 -c 推理前沿       添加并下载一篇
  papers --bilingual 2501.12948      生成中英对照材料
  papers --bilingual all             生成全部(已生成的自动跳过)
  papers -b all -f                   强制重建全部中英对照材料
  papers --list                      查看清单与状态
  papers --wiki-link 1706.03762 wiki/wiki/sources/vaswani-2017-attention-is-all-you-need.md
                                      标记一篇已进 LLM Wiki(--list 显示 ⬡)

（也可继续用 `python fetch_papers.py ...`，两者等价）"""


def build_parser() -> argparse.ArgumentParser:
    # add_help 保持默认的 True:之前设成 False 又没别的参数占用 -h,
    # 结果 --help/-h 一律报 "unrecognized arguments",帮助只能靠不带参数触发。
    ap = argparse.ArgumentParser(
        prog="papers",
        description="arXiv 论文下载脚手架:下载 PDF、生成中英对照阅读材料",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG)
    ap.add_argument("papers", nargs="*", help="arXiv id 或 arxiv.org 链接")
    ap.add_argument("-c", "--category", default=None, help="新增论文的分类(目录名)")
    ap.add_argument("-a", "--all", action="store_true", help="下载清单中所有未落盘论文")
    ap.add_argument("-f", "--force", action="store_true",
                    help="已存在也重新下载/重新生成(对 --all 与 --bilingual 都生效)")
    ap.add_argument("-l", "--list", action="store_true", help="列出清单")
    ap.add_argument("--wiki-link", nargs=2, metavar=("ID", "PAGE"),
                    help="标记一篇论文已进 LLM Wiki:PAGE 为 source 页相对路径"
                         "(如 wiki/wiki/sources/xxx.md),--list 显示 ⬡")
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
    return ap


def _summary(failed: int, total: int) -> int:
    """把「失败篇数 / 总数」翻译成退出码。"""
    if failed == 0:
        return 0
    return 1 if failed >= total else 2


def _cmd_list(reg: dict, settings: Settings) -> int:
    """本地操作,不联网。"""
    for row in paper_rows(reg, settings):
        log(row)
    log(summary_line(reg))
    return 0


def _cmd_wiki_link(reg: dict, settings: Settings, arxiv_id: str,
                   page_path: str) -> int:
    """本地操作,不联网:回填 papers.json 的 wiki 字段做「已进 wiki」标记。

    真正的 ingest 与关系创建在 LLM Wiki 里手动完成,这里只负责标记这一笔。
    """
    try:
        link_wiki(arxiv_id, page_path, reg, settings)
    except PaperKitError as e:
        log(f"! {e}")
        return 3
    if not (settings.base_dir / Path(page_path)).exists():
        log(f"  ! 注意:{page_path} 尚不存在,文件落盘后 --list 的 ⬡ 才亮")
    log(f"✓ 已标记 {arxiv_id} → {page_path}")
    return 0


def _cmd_bilingual(reg: dict, settings: Settings, target: str,
                   download_images: bool, force: bool) -> int:
    """生成中英对照材料。已生成的默认跳过,只对未完成的计数与报告。

    过滤放在这里而不是全交给 build_bilingual,是为了让 [i/n] 的进度反映
    「本次真正要做多少篇」;build_bilingual 内部仍会再判断一次,以防直接
    调用该 API 的人绕过 CLI。
    """
    ids = target_ids(target, reg)
    known = {p["id"]: p for p in reg["papers"]}
    if force:
        pending, skipped = ids, 0
    else:
        pending = [i for i in ids
                   if not is_generated(known.get(i, {}), settings)]
        skipped = len(ids) - len(pending)

    if skipped:
        log(f"跳过 {skipped} 篇已生成(-f/--force 可重建)")
    if not pending:
        log("没有需要生成的论文。")
        return 0

    failed = 0
    for i, pid in enumerate(pending, 1):
        log(f"[{i}/{len(pending)}] 生成中英对照 {pid}")
        try:
            build_bilingual(pid, reg, settings,
                            download_images=download_images, force=force)
        except PaperKitError as e:      # 单篇失败不拖垮整批
            log(f"  ✗ 失败: {e}")
            failed += 1
        if i < len(pending):
            time.sleep(3)
    return _summary(failed, len(pending))


def _cmd_download_all(reg: dict, settings: Settings, force: bool) -> int:
    if not reg["papers"]:
        log("papers.json 为空,先用 `papers <id>` 添加论文。")
        return 0
    ok = 0
    dirty = False
    total = len(reg["papers"])
    for i, p in enumerate(reg["papers"], 1):
        if "file" not in p:  # 清单里只登记了 id,先补全元数据
            log(f"[{i}/{total}] {p['id']} (拉取元数据...)")
            if not ensure_metadata(p, settings):
                log("  ! 元数据未取到,本条跳过(下次 --all 会重试)")
                time.sleep(3)
                continue
            dirty = True
            time.sleep(3)
        else:
            log(f"[{i}/{total}] {p['id']}")
        if download_entry(p, settings, force=force) != "failed":
            ok += 1
        time.sleep(3)  # arXiv 限流:请求间隔 ≥3s
    if dirty:
        save_registry(reg, settings)
    log(f"\n完成:{ok}/{total} 篇可用,存于 {settings.out_dir}")
    return _summary(total - ok, total)


def _cmd_add(reg: dict, settings: Settings, texts: list[str],
             category: str | None, force: bool, parser) -> int:
    if not texts:
        parser.print_help()
        return 0
    known = {p["id"]: p for p in reg["papers"]}
    added, ok = 0, 0
    for i, text in enumerate(texts):
        entry = resolve_entry(text, category, settings)
        if entry is None:
            continue
        existing = known.get(entry["id"])
        if existing is None:
            reg["papers"].append(entry)
            known[entry["id"]] = entry
            added += 1
        else:
            # 已登记的条目可能是当初元数据没取到的「半成品」(只存了 id),
            # 这次拿到了就回填——否则 PDF 按正确名字落了盘,登记表却永远
            # 停在半成品状态:--list 一直显示「待补全元数据」,--all 每次重试。
            # 只补缺失字段,绝不覆盖已有的 file:PDF 已按旧名字落盘,
            # 改掉 file 就等于指向一个不存在的文件。
            for key in ("title", "authors", "year", "file"):
                if key not in existing and key in entry:
                    existing[key] = entry[key]
            entry = existing
        log(f"[{i + 1}/{len(texts)}] {entry['id']} - "
            f"{entry.get('title', '(元数据待补全)')[:60]}")
        if "file" not in entry:
            continue  # 元数据没拿到,下次 --all 再补全并下载
        if download_entry(entry, settings, force=force) != "failed":
            ok += 1
        if i < len(texts) - 1:
            time.sleep(3)
    save_registry(reg, settings)
    log(f"\n新增登记 {added} 篇,本次成功 {ok} 篇,存于 {settings.out_dir}")
    return 0


def run(argv: list[str] | None = None, env: dict | None = None,
        base_dir=None) -> int:
    """可测试的入口:argv / env / base_dir 都可注入,不读全局。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings.from_values(
        base_dir=base_dir,
        proxy=args.proxy,
        translator=args.translator,
        base_url=args.translate_base_url,
        model=args.translate_model,
        api_key=args.translate_api_key,
        env=env,
    )

    reg = load_registry(settings)

    # ---- 模式一:--list,本地操作,不联网 ----
    if args.list:
        return _cmd_list(reg, settings)

    # ---- 模式二:--wiki-link,回填 wiki 状态,本地操作 ----
    if args.wiki_link:
        return _cmd_wiki_link(reg, settings, args.wiki_link[0],
                              args.wiki_link[1])

    # ---- 模式三:--bilingual,生成中英对照材料 ----
    if args.bilingual:
        return _cmd_bilingual(reg, settings, args.bilingual,
                              not args.no_images, args.force)

    # ---- 模式四:--all,批量补齐 PDF ----
    if args.all:
        return _cmd_download_all(reg, settings, args.force)

    # ---- 模式五:位置参数,添加并下载指定论文 ----
    return _cmd_add(reg, settings, args.papers, args.category, args.force, parser)


def main() -> int:
    # Windows 控制台默认 GBK,打印 ✓/⚠ 等字符会崩,强制切到 UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        return run()
    except PaperKitError as e:
        log(f"! {e}")
        return 3
