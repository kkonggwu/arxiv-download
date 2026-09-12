"""领域层:纯规则与纯渲染,零副作用。

硬约束(由 tests/test_layering.py 在 CI 层强制):
  * 不 import infra / services / cli
  * 不读写文件、不发网络请求、不读环境变量
因此本层的所有函数都可以完全离线、零打桩地测试。
"""

from .arxiv_id import NEW_ID, OLD_ID, parse_arxiv_id
from .glossary import ACRONYM_FIX, SECTION_ZH, fix_acronyms
from .html_parser import MIN_PARA_CHARS, PaperHTMLParser, parse_blocks
from .markdown import (SKIP_TITLE_CLASS, TITLE_LEVEL, heading_level,
                       render_code_block, render_equation_rows, render_table)
from .naming import make_filename, sanitize

__all__ = [
    "NEW_ID", "OLD_ID", "parse_arxiv_id",
    "ACRONYM_FIX", "SECTION_ZH", "fix_acronyms",
    "MIN_PARA_CHARS", "PaperHTMLParser", "parse_blocks",
    "SKIP_TITLE_CLASS", "TITLE_LEVEL", "heading_level",
    "render_code_block", "render_equation_rows", "render_table",
    "make_filename", "sanitize",
]
