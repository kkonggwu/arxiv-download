"""`--list` 的行渲染。

放在 services 而不是 cli,是为了让「✓ 看磁盘、◈ 也看磁盘」这条有回归测试
的行为可以被直接断言,而不必去抓 stdout。
"""

from ..config import Settings
from ..domain import sanitize
from .bilingual import is_generated


def paper_rows(reg: dict, settings: Settings | None = None) -> list[str]:
    """返回逐行的清单状态文本(不含结尾汇总行)。

    ✓ = PDF 已落盘;◈ = 中英对照已生成。两个标记都查磁盘而不只看登记表
    字段——否则手工删掉 md 之后,--list 仍会谎报已生成。◈ 与
    build_bilingual 的跳过判断共用 is_generated,避免两处口径漂移。
    """
    s = settings or Settings()
    rows = []
    for p in reg["papers"]:
        cat = p.get("category", "未分类")
        # ◈ 与 ✓ 是两个独立维度:元数据没补全不等于没生成过对照材料
        # (元数据接口限流时就会这样,实测过 2201.11903)。所以先算 ◈,
        # 再决定走「待补全元数据」还是正常行。
        bi = "◈" if is_generated(p, s) else " "
        if "file" not in p:          # 元数据还没补全的条目
            rows.append(f" [ {bi}] {cat:<10} {p['id']} (待补全元数据)")
            continue
        path = s.out_dir / sanitize(cat) / p["file"]
        mark = "✓" if path.exists() else " "
        rows.append(f" [{mark}{bi}] {cat:<10} {p['file']}")
    return rows


def summary_line(reg: dict) -> str:
    return f"\n共 {len(reg['papers'])} 篇(◈ = 已生成中英对照)"
