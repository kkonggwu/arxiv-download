"""wiki 关联状态:跟踪「哪篇论文已经进了 LLM Wiki 知识库」。

paperkit 只负责「收集 + 翻译」,论文进不进知识库、以及知识库里的关系
创建,都由人手动在 LLM Wiki 里完成。这里只提供两件事:

  * is_in_wiki —— 判断某篇是否已进 wiki(登记表有 wiki 字段 + 文件在磁盘上)
  * link_wiki  —— 手动 ingest 完后,回填 papers.json 的 wiki 字段做标记

登记表的 wiki 字段存的是 source 页相对项目根的路径,如
`wiki/wiki/sources/vaswani-2017-attention-is-all-you-need.md`。缺省为空 = 未进 wiki。
"""

from pathlib import Path

from ..config import Settings
from ..domain import parse_arxiv_id
from ..errors import ConfigError
from ..infra.storage import RegistryStore


def is_in_wiki(entry: dict, settings: Settings | None = None) -> bool:
    """该条目是否已在 LLM Wiki 里建立了 source 页。

    与 is_generated 同一口径:登记表有 wiki 字段 **且** 文件确实在磁盘上。
    只看字段的话,手工删掉 source 页之后 --list 仍会谎报已入库。
    """
    s = settings or Settings()
    rel = entry.get("wiki")
    return bool(rel) and (s.base_dir / Path(rel)).exists()


def link_wiki(arxiv_id: str, page_path: str, reg: dict,
              settings: Settings | None = None) -> dict:
    """把一篇已登记论文标记为「已进 wiki」,回填 wiki 字段并原子写回。

    arxiv_id 支持 id 或链接(走 parse_arxiv_id 归一化,统一去掉 vN 后缀)。
    page_path 是 source 页相对项目根的路径。该 id 不在清单时抛 ConfigError
    ——它应该先用 `papers <id>` 登记过,否则无从标记。
    """
    s = settings or Settings()
    pid = parse_arxiv_id(arxiv_id) or arxiv_id.strip()
    for entry in reg["papers"]:
        if entry.get("id") == pid:
            entry["wiki"] = page_path
            RegistryStore(s.registry_path).save(reg)
            return entry
    raise ConfigError(f"清单里没有 {pid},先用 `papers {pid}` 登记")
