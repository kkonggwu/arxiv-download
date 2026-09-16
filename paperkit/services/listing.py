"""`--list` 的行渲染。

放在 services 而不是 cli,是为了让「✓ 看磁盘、◈ 也看磁盘」这条有回归测试
的行为可以被直接断言,而不必去抓 stdout。
"""

from ..config import Settings
from ..domain import sanitize
from .bilingual import is_generated
from .wiki import is_in_wiki


def paper_rows(reg: dict, settings: Settings | None = None) -> list[str]:
    """返回逐行的清单状态文本(不含结尾汇总行)。

    ✓ = PDF 已落盘;◈ = 中英对照已生成;⬡ = 已进 wiki。三个标记都查磁盘而
    不只看登记表字段——否则手工删掉 md 之后,--list 仍会谎报已生成/已入库。
    ◈ 与 build_bilingual 的跳过判断共用 is_generated,⬡ 与 wiki.link_wiki 的
    回填字段共用 is_in_wiki,避免口径漂移。
    """
    s = settings or Settings()
    rows = []
    for p in reg["papers"]:
        cat = p.get("category", "未分类")
        # 三个标记是三个独立维度:元数据没补全不等于没生成过对照材料,
        # 生成过对照材料也不等于进了 wiki。所以三个都算,再决定走
        # 「待补全元数据」还是正常行。
        bi = "◈" if is_generated(p, s) else " "
        wi = "⬡" if is_in_wiki(p, s) else " "
        if "file" not in p:          # 元数据还没补全的条目
            rows.append(f" [ {bi}{wi}] {cat:<10} {p['id']} (待补全元数据)")
            continue
        path = s.out_dir / sanitize(cat) / p["file"]
        mark = "✓" if path.exists() else " "
        rows.append(f" [{mark}{bi}{wi}] {cat:<10} {p['file']}")
    return rows


def summary_line(reg: dict) -> str:
    return (f"\n共 {len(reg['papers'])} 篇"
            "(✓ 已下载 · ◈ 已生成双语 · ⬡ 已进 wiki)")
