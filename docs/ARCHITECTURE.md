# 模块化重构设计方案

> 目标：把 `fetch_papers.py`（1218 行单文件）拆成**分层清晰、可独立测试、可增量迁移**的
> 标准 Python 包，同时保留「零第三方运行时依赖」这一核心特性。
> 本文只描述设计与迁移路线，不改动行为。

---

## 1. 现状诊断

先量化，再开方。以下数据由 AST 统计 `fetch_papers.py` 得到：

| 指标 | 实测值 | 评价 |
|---|---|---|
| 文件行数 | 1218 | 单文件超过 500 行后定位成本陡增 |
| 顶层符号 | 30（29 函数 + 1 类） | 平面命名空间，无分组 |
| 最长单元 | `PaperHTMLParser` 218 行、`main` 137 行、`build_bilingual` 130 行 | 三者合计占总代码 40% |
| 第三方依赖 | 0（12 个 stdlib 模块） | ✅ 优点，必须保留 |
| 回归测试 | 53 个，全部离线 | ✅ 优点，是重构的安全网 |
| 模块级可变全局 | 5 个：`PROXY` / `TRANSLATE_BACKEND` / `OPENAI_BASE_URL` / `OPENAI_MODEL` / `TRANSLATE_API_KEY` | ❌ 主要痛点 |
| `global` 声明 | 1 处（在 `main()` 内一次性改写上述 5 个） | ❌ 见下 |

### 1.1 四个结构性问题

**问题 A：配置靠全局变量传递。**
`_translate_google()` / `_translate_openai()` / `http_get()` 都直接读模块级全局。
后果是单元测试必须先改全局再跑（测试之间隐式共享状态、无法并行），且
「同一进程内用两种后端翻译」在架构上不可能。

**问题 B：网络、解析、渲染、编排、CLI 五件事耦合在一个文件里。**
`build_bilingual()` 同时干了：读缓存 → 发 HTTP → 解析 HTML → 调翻译接口 →
拼 Markdown → 下载图片 → 回写登记表。想单独测「拼 Markdown 的格式」，
就得先构造一整套网络桩。

**问题 C：异常语义扁平。**
`build_bilingual` 捕获的是 `RuntimeError`（`translate_one` 抛的）；
`fetch_paper_html` 在 arXiv 与 ar5iv 都失败时抛 `RuntimeError`。
调用方无法区分「网络抖动可重试」和「这篇论文没有 HTML 版，重试也没用」。

**问题 D：副作用分散且不可注入。**
缓存路径、登记表路径、输出目录、`time.sleep(0.4)` 的节流、`sys.stdout.reconfigure`
散落在各函数里。测试只能靠 `mock.patch.object(fp, "BILINGUAL_DIR")` 这类字符串
打补丁（现有测试正是这么做的，共 3 处），脆弱且易漏。

### 1.2 不打算改的东西（明确保留）

- **零运行时依赖**：只用 stdlib。这不是将就，而是这个脚本能在任何有 Python 的机器上直接跑的原因。
- **单命令 CLI 形态**：`python fetch_papers.py --bilingual all` 继续可用，迁移期用「薄壳」兼容。
- **缓存以英文原文为 key**：已验证的设计，重构不得改变缓存 key 的语义，否则用户已有缓存全部失效。
- **53 个测试的断言**：是重构的正确性判据，不是负担。

---

## 2. 设计原则

1. **依赖单向**：`cli → services → domain`，`infra` 被 services 通过接口调用。domain 谁都不依赖。
2. **副作用在边缘**：domain 层是纯函数——给定输入必有确定输出，不碰磁盘、不碰网络、不读全局。
3. **契约先于实现**：层与层之间只通过 `dataclass` / `Protocol` 交互，不传裸 `dict`。
4. **依赖注入而非全局**：`Settings` 对象显式传入，`Translator` 与 `HttpClient` 通过参数注入。
5. **每步可交付**：迁移分 6 个阶段，每个阶段结束时测试全绿、可单独提交、可随时停手。
6. **不过度设计**：不引入 DI 框架、不引入 ORM、不拆微服务。这是个人论文工具，不是 SaaS。

---

## 3. 目标架构

### 3.1 分层图

```
┌─────────────────────────────────────────────────────────┐
│  cli/          入口层：解析参数、装配依赖、决定退出码      │
│                main.py · commands/{download,bilingual,list}│
└──────────────────────────┬──────────────────────────────┘
                           │ 只调用 services，只依赖 config
┌──────────────────────────▼──────────────────────────────┐
│  services/     应用层：编排用例，持有事务边界              │
│    download.py   拉元数据 + 下 PDF + 回写登记表            │
│    bilingual.py  读缓存 → 翻译 → 拼装 → 落盘              │
│    images.py     插图本地化                                │
└───────┬──────────────────────────────────┬──────────────┘
        │ 调用 domain（纯逻辑）              │ 调用 infra（副作用）
┌───────▼──────────────────┐   ┌───────────▼──────────────┐
│  domain/   领域层（纯函数）│   │  infra/   基础设施层       │
│    arxiv_id.py   id 解析   │   │   http.py     请求+代理   │
│    naming.py     文件名     │   │   arxiv_api.py Atom 拉取  │
│    html_parser.py 块抽取   │   │   registry.py 登记表读写  │
│    markdown.py   渲染      │   │   cache.py    翻译缓存    │
│    glossary.py   术语表    │   │   translate/  后端实现    │
│    models.py     数据契约  │   │   logging.py  日志        │
└──────────────────────────┘   └──────────────────────────┘
        ▲                                    ▲
        └────────── config.py（Settings）─────┘
```

**关键约束**：`domain` 不 import `infra`；`infra` 不 import `services`；`cli` 不直接 import `infra`。

### 3.2 目标目录树

```
06.论文/
├── fetch_papers.py              # 迁移期薄壳（P4 后删除或保留为 3 行转发）
├── pyproject.toml               # 打包 + 工具配置（新增）
├── papers.json                  # 数据，位置不变
├── src/paperkit/
│   ├── __init__.py
│   ├── config.py                # Settings dataclass（替代 5 个全局）
│   ├── errors.py                # 异常层级
│   ├── domain/
│   │   ├── models.py            # PaperMeta / PaperEntry / Block / HtmlSource
│   │   ├── arxiv_id.py          # parse_arxiv_id（NEW_ID/OLD_ID 正则）
│   │   ├── naming.py            # sanitize / make_filename
│   │   ├── html_parser.py       # PaperHTMLParser / parse_blocks / heading_level
│   │   ├── markdown.py          # render_table / render_code_block / render_equation_rows
│   │   └── glossary.py          # SECTION_ZH / ACRONYM_FIX / fix_acronyms
│   ├── infra/
│   │   ├── http.py              # HttpClient（含代理、超时、重试）
│   │   ├── arxiv_api.py         # 拉 Atom / 拉 HTML，返回原始 bytes/str
│   │   ├── registry.py          # RegistryStore.load/save
│   │   ├── cache.py             # TranslationCache（增量落盘、失败标记清理）
│   │   ├── logging.py           # get_logger（替代全局 log()）
│   │   └── translate/
│   │       ├── base.py          # Translator Protocol
│   │       ├── google.py
│   │       └── openai.py
│   ├── services/
│   │   ├── download.py
│   │   ├── bilingual.py
│   │   └── images.py
│   └── cli/
│       ├── main.py              # build_parser / run / main
│       └── commands/
│           ├── download.py
│           ├── bilingual.py
│           └── listing.py
├── tests/
│   ├── domain/                  # 纯函数测试，无 mock
│   ├── infra/                   # 用 fake transport
│   ├── services/                # 用 fake HttpClient + FakeTranslator
│   └── test_layering.py         # 架构约束测试（见 §6）
└── docs/
    └── ARCHITECTURE.md          # 本文
```

### 3.3 模块清单与迁移映射

每个模块的**行数目标 ≤ 250**，超出即视为需要再拆。

| 目标模块 | 来源（当前行号） | 职责 | 依赖 |
|---|---|---|---|
| `config.py` | 52–61、301–317 | `Settings` 不可变配置对象 | 无 |
| `errors.py` | 新增 | 异常层级 | 无 |
| `domain/models.py` | 新增 | 全部数据契约 | 无 |
| `domain/arxiv_id.py` | 128–148 | 两代 arXiv id 解析 | 无 |
| `domain/naming.py` | 189–214 | `sanitize` / `make_filename` | 无 |
| `domain/glossary.py` | 320–345 | 术语表 + `fix_acronyms` | 无 |
| `domain/markdown.py` | 347–461 | 表格/代码块/公式/标题级渲染 | `models` |
| `domain/html_parser.py` | 463–744 | `PaperHTMLParser` + `parse_blocks` | `models`, `markdown` |
| `infra/logging.py` | 67–70 | logger 工厂 | 无 |
| `infra/http.py` | 72–104 | GET/POST JSON、代理、超时 | `errors`, `config` |
| `infra/arxiv_api.py` | 150–184、683–709 | Atom 元数据、HTML 抓取（含 ar5iv 回退） | `http`, `errors` |
| `infra/registry.py` | 109–121 | 登记表读写 | `models`, `errors` |
| `infra/cache.py` | 975–982、1000–1012 | 翻译缓存（分后端、增量落盘） | `errors` |
| `infra/translate/*` | 746–846 | 翻译后端 + 分句 | `http`, `errors` |
| `services/download.py` | 219–287 | 单篇下载用例 | `arxiv_api`, `registry`, `naming` |
| `services/bilingual.py` | 943–1073 | 生成对照材料用例 | 上面全部 |
| `services/images.py` | 848–941 | 插图本地化 | `http`, `naming` |
| `cli/main.py` | 1078–1218 | 参数解析、装配、退出码 | `services`, `config` |

---

## 4. 数据契约

用 `@dataclass` 替换裸 `dict`。这是整个重构收益最大的一步：现在
`entry` 到底是「登记表行」还是「元数据」还是两者合并，全靠读代码猜。

```python
# domain/models.py
from dataclasses import dataclass, field
from typing import Literal

@dataclass(frozen=True, slots=True)
class PaperMeta:
    """arXiv Atom API 的规范化结果。fetch 失败时不构造此对象。"""
    id: str
    title: str
    authors: tuple[str, ...]        # 已在源头按首次出现去重
    year: str
    summary: str = ""
    primary_category: str | None = None

@dataclass(slots=True)
class PaperEntry:
    """papers.json 中的一行。meta 为 None 表示元数据尚未补全。"""
    id: str
    category: str = "未分类"
    file: str | None = None         # PDF 文件名；None = 待补全
    bilingual: str | None = None    # 对照 md 的相对路径
    meta: PaperMeta | None = None

    def to_json(self) -> dict: ...
    @classmethod
    def from_json(cls, raw: dict) -> "PaperEntry": ...

BlockKind = Literal["h2","h3","h4","h5","h6","p","cap",
                    "table","verbatim","formula","image"]

@dataclass(frozen=True, slots=True)
class Block:
    kind: BlockKind
    text: str

@dataclass(frozen=True, slots=True)
class HtmlSource:
    html: str
    name: Literal["arxiv", "ar5iv"]   # 来源，用于日志与图片基址选择
    image_base: str
```

**契约不变式**（写进测试）：

1. `PaperMeta` 一定不含占位值——失败返回 `None`，绝不返回 `title=id` 的对象。
   （这条对应已修的 ERR：元数据失败固化占位文件名）
2. `PaperEntry.file is None` ⟺ 元数据未补全 ⟺ `--all` 应当重试。
3. `Block.kind == "image"` 时 `text` 是 Markdown 图片语法，不是裸 URL。
4. 缓存 key 恒为英文原文 `str`，值恒为成功译文 `str`；永不出现 `⚠` 前缀值。

### 4.1 两个 Protocol

```python
# infra/translate/base.py
class Translator(Protocol):
    name: str
    def translate(self, text: str) -> str: ...
    def close(self) -> None: ...

# infra/http.py
class Transport(Protocol):
    def get(self, url: str, timeout: float = 60) -> bytes: ...
    def post_json(self, url: str, payload: dict,
                  headers: dict | None = None, timeout: float = 60) -> dict: ...
```

`Transport` 是为了测试：`FakeTransport` 返回预置字节，零网络、零 `mock.patch`。

---

## 5. 错误与日志策略

### 5.1 异常层级

```
PaperKitError(Exception)                 # 基类，CLI 统一捕获
├── ConfigError                          # 参数/环境变量非法 → 退出码 3
├── NetworkError                         # 连接/超时/5xx，重试耗尽 → 可重试
├── SourceUnavailable(PaperKitError)     # arXiv 与 ar5iv 都没有 HTML → 不可重试
├── ParseError                           # HTML 结构异常，抽不出块
├── TranslateError                       # 单段翻译失败（替代现在的 RuntimeError）
├── RegistryError                        # papers.json 读写/格式错误
└── AssetError                           # 单张插图下载失败（可降级，不中断）
```

**关键区分**：`NetworkError` 可重试，`SourceUnavailable` 不可重试。
现在两者都是 `RuntimeError`，`--bilingual all` 只能一律记失败。

### 5.2 日志

`log()` 全局函数改为 `logging.getLogger("paperkit")`，并在 CLI 层配置 handler：

- 正常输出 → stdout，`INFO`
- `-v/--verbose` → `DEBUG`
- `-q/--quiet` → `WARNING`
- 保留 `sys.stdout.reconfigure(encoding="utf-8")`，但移到 `cli/main.py` 的 `run()` 开头

**退出码约定**：

| 码 | 含义 |
|---|---|
| 0 | 全部成功 |
| 1 | 全部失败 |
| 2 | 部分失败（批量模式下单篇失败不拖垮整批，沿用现行为） |
| 3 | 参数或配置错误 |

---

## 6. 依赖方向与自动化护栏

### 6.1 依赖矩阵

| 从 ↓ / 到 → | config | errors | domain | infra | services | cli |
|---|---|---|---|---|---|---|
| **config** | — | ✅ | ❌ | ❌ | ❌ | ❌ |
| **errors** | ❌ | — | ❌ | ❌ | ❌ | ❌ |
| **domain** | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **infra** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **services** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **cli** | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |

### 6.2 用测试锁死架构

不引入 `import-linter`（避免依赖），直接写一个 30 行的 AST 测试：

```python
# tests/test_layering.py
import ast, pathlib, pytest

SRC = pathlib.Path(__file__).parent.parent / "src" / "paperkit"
ALLOWED = {
    "config":   {"config", "errors"},
    "errors":   {"errors"},
    "domain":   {"domain", "errors"},
    "infra":    {"infra", "domain", "config", "errors"},
    "services": {"services", "infra", "domain", "config", "errors"},
    "cli":      {"cli", "services", "config", "errors"},
}

def _layer(path):
    return path.relative_to(SRC).parts[0].removesuffix(".py")

def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("paperkit"):
            yield node.module.split(".")[1] if "." in node.module else "paperkit"
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("paperkit"):
                    yield a.name.split(".")[1]

def test_no_illegal_cross_layer_import():
    for py in SRC.rglob("*.py"):
        src_layer = _layer(py)
        for dep in _imports(py):
            assert dep in ALLOWED[src_layer], f"{py.name}: {src_layer} 不得依赖 {dep}"
```

这样「domain 不许碰网络」不是靠自觉，而是 CI 会红。

---

## 7. 配置策略

```python
# config.py
@dataclass(frozen=True, slots=True)
class Settings:
    base_dir: Path
    registry_path: Path
    out_dir: Path
    bilingual_dir: Path
    cache_dir: Path
    translator: str = "google"
    translate_retries: int = 3
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    api_key: str | None = None
    proxy: str | None = None
    download_images: bool = True
    cache_flush_every: int = 20
    request_delay: float = 0.4
    min_para_chars: int = 40

    @classmethod
    def from_cli(cls, args, env=os.environ) -> "Settings":
        """覆盖优先级：CLI > 环境变量 > 默认值（沿用现语义）"""
```

- **不读全局**：`Settings` 由 `cli` 构造，逐层传参。
- **测试友好**：`Settings(base_dir=tmp_path)` 即可，不用再 `patch.object` 五个模块变量。
- **不变式**：`frozen=True` 防止中途被改写（现在 `main()` 里那处 `global` 正是隐患）。

---

## 8. 测试策略

现有 53 个测试按层归位，断言内容基本不变：

| 现有测试类 | 去向 | 改动 |
|---|---|---|
| `TestArxivIds` | `tests/domain/test_arxiv_id.py` | 仅改 import |
| `TestHeadingLevels` | `tests/domain/test_markdown.py` | 仅改 import |
| `TestTableParsing` | `tests/domain/test_html_parser.py` | 仅改 import |
| `TestImageExtraction` | `tests/domain/test_html_parser.py` | 仅改 import |
| `TestMetadata` | `tests/infra/test_arxiv_api.py` | 注入 `FakeTransport` |
| `TestImageLocalization` | `tests/services/test_images.py` | 传 `Settings(tmp_path)` |
| `TestBilingualCache` | `tests/services/test_bilingual.py` | 去掉 `patch.object(fp,"BASE")` |

**净新增测试**：

1. `test_layering.py`（§6.2）——架构护栏
2. `test_models.py`——`PaperEntry` 往返 JSON、契约不变式 §4.1 的四条
3. `test_settings.py`——三层覆盖优先级（CLI > env > 默认）
4. `test_translator_contract.py`——同一组输入跑 `FakeTranslator` 与两个真实后端类
   （后者用 `FakeTransport` 打桩），验证 `Translator` Protocol 一致
5. **特征测试（characterization test）**：迁移前，对一篇已生成的对照 md 做快照比对。
   重构后输出必须逐字节一致——这是防止「拆着拆着格式变了」的最后一道闸。

---

## 9. 打包与 CI

### 9.1 `pyproject.toml`

```toml
[project]
name = "paperkit"
version = "0.2.0"
requires-python = ">=3.11"
dependencies = []                 # 运行时零依赖，这是硬约束

[project.optional-dependencies]
dev = ["pytest", "ruff", "mypy"]

[project.scripts]
papers = "paperkit.cli.main:run"  # 装完可直接 `papers --all`

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = false
warn_unused_ignores = true
```

**兼容性**：迁移期 `fetch_papers.py` 保留为薄壳——

```python
"""兼容入口。逻辑已迁移到 src/paperkit/，此文件仅为保留原有命令习惯。"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))
from paperkit.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
```

这样 README 里所有 `python fetch_papers.py ...` 命令继续可用，用户无感。

### 9.2 CI（GitHub Actions）

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest]
    python: ["3.11", "3.12", "3.13"]
steps:
  - ruff check .
  - ruff format --check .
  - mypy src/paperkit
  - python -m pytest -q
```

**CI 无需网络**——53 个测试全部离线，这是当前项目难得的优势，重构必须保住。
Windows 进矩阵是因为 `sys.stdout.reconfigure`、路径分隔符、GBK 编码这些坑只在 Windows 出现。

---

## 10. 分阶段迁移路线

每阶段**独立提交、测试全绿、可随时叫停**。这是「保持 git 版本阶段性保存」的落地方式。

### P0 — 建骨架与配置对象（不动业务逻辑）

- 建 `src/paperkit/` 包结构，`config.py`、`errors.py`、`domain/models.py` 落地
- `fetch_papers.py` 里把常量改为从 `Settings` 读，但**函数体一行不改**
- 新增 `tests/test_settings.py`
- **验收**：53 测试全绿 + 新测试通过；`--list` 输出逐字符不变
- 提交：`refactor(P0): 引入 Settings 与包骨架，业务逻辑未变`

### P1 — 抽离 infra（副作用集中）

- 抽 `http.py`（引入 `Transport` Protocol）、`registry.py`、`logging.py`
- 抽 `translate/`（`Translator` Protocol + 两个实现），**顺手把 `RuntimeError` 换成 `TranslateError`**
- 新增 `tests/infra/`、`FakeTransport`
- **验收**：`test_translator_contract.py` 通过；后端切换不再依赖全局变量
- 提交：`refactor(P1): 抽离 http/registry/translate 到 infra 层`

### P2 — 抽离 domain（纯函数化）

- 抽 `arxiv_id.py`、`naming.py`、`glossary.py`、`markdown.py`、`html_parser.py`
- domain 层不出现 `open()` / `urlopen` / `Path.write_text`
- **验收**：`tests/domain/` 里**零 `mock`**——纯函数测试不需要打桩
- 提交：`refactor(P2): 抽离 domain 纯逻辑层`

### P3 — 抽离 services 与 cli

- 抽 `services/{download,bilingual,images}.py`、`cli/main.py` + 三个命令
- `fetch_papers.py` 变薄壳
- 新增 `tests/services/`，用 `FakeTransport` + `FakeTranslator`
- **验收**：端到端跑通一篇（`2501.12948`），与 P2 输出**逐字节一致**
- 提交：`refactor(P3): 抽离 services 与 cli，入口改为薄壳`

### P4 — 收口与护栏

- 新增 `tests/test_layering.py`、`pyproject.toml`、CI 配置
- 补 `ruff` / `mypy` 并清零告警
- 更新 README 的文件结构与开发命令
- 提交：`chore(P4): 补架构护栏测试、打包配置与 CI`

### P5 — 重构后才做的功能（可选，各自独立提交）

这些是此前评审中**刻意延后**的项，重构完成后才容易做：

| 项 | 为何重构后才做 | 状态 |
|---|---|---|
| `--bilingual all` 跳过已生成 | 需要 `BilingualService` 暴露「是否已完成」查询 | **已完成**（2026-09-14） |
| 断点续传 / Range 下载 | 需要 `HttpClient` 支持自定义 header | 待做 |
| 版本号固定（不剥 `vN`） | 需要 `PaperEntry` 增加 `version` 字段 | 待做 |
| 引用编号可跳转 | 需要解析阶段保留 `ltx_bibliograph` 结构 | 待做 |
| ~~并发下载（线程池）~~ | ~~需要 `Settings` 无共享可变状态~~ | **撤销** |

「并发下载」一项撤销,理由是它与 §12「不做异步」自相矛盾——那里给出的理由
(`time.sleep(0.4)` 的节流下收益接近零)对线程池同样成立,而且 arXiv 对抓取
频率有明确要求,并发有被封 IP 的风险。这一项不该做,而不是延后做。

---

## 11. 风险与回退

| 风险 | 概率 | 应对 |
|---|---|---|
| 重构中格式漂移（输出变了但测试没覆盖） | 中 | P0 前先做**快照特征测试**，逐字节比对 |
| `slots=True` 与 Python 3.10 不兼容 | 低 | `requires-python = ">=3.11"`，本机 3.13 |
| 薄壳 `sys.path` 注入在多平台出问题 | 低 | P4 后推荐 `pip install -e .`，薄壳仅作兜底 |
| 迁移到一半停手留下双份代码 | 中 | 每阶段独立可用；最坏停在 P2，domain 已可独立复用 |
| 缓存 key 语义被改导致用户缓存失效 | 低 | §4.1 不变式 4 写成测试 |

**回退策略**：每阶段一个 commit，出问题 `git revert` 单个 commit 即可，
不需要回退整轮重构。

---

## 12. 明确不做（YAGNI）

- ❌ 不引入 `requests` / `httpx`——stdlib `urllib` 够用，零依赖是卖点
- ❌ 不引入 DI 框架（`dependency-injector` 等）——手工传参已经够清晰
- ❌ 不做插件系统——两个翻译后端用 `Protocol` 足够
- ❌ 不改 CLI 参数名——用户肌肉记忆是资产
- ❌ 不做异步——`time.sleep(0.4)` 的节流下，`asyncio` 收益接近零

---

## 13. 收益预估

| 维度 | 现状 | 重构后 |
|---|---|---|
| 最大文件 | 1218 行 | ≤ 250 行 |
| 最大函数 | 218 行 | ≤ 120 行 |
| 可变全局 | 5 个 | 0（`Settings` 不可变） |
| 测试打桩点 | 3 处 `patch.object` | 0（全走注入） |
| 新增后端成本 | 改 5 处 + 加全局 | 加 1 个文件 + 注册表 1 行 |
| 纯逻辑可测性 | 需构造网络桩 | 纯函数直测 |
| 架构违规检测 | 人工 review | CI 自动拦截 |

---

*本文档只描述设计。具体执行按 §10 阶段推进，每阶段独立提交并保持测试全绿。*

---

## 附:实施记录(2026-09-12)

P0–P4 已全部落地,提交序列 `8ace343` → `aa25d78` → `9b5c643` → `49f0678` → 本文档所在提交。
每阶段独立提交且测试全绿。

### 实测收益(对照 §13)

| 维度 | 重构前 | 目标 | **实测** |
|---|---|---|---|
| 最大文件 | 1218 行 | ≤ 250 行 | **287 行**(`domain/html_parser.py`) |
| 最大函数 | 218 行 | ≤ 120 行 | 218 行(`PaperHTMLParser`,见下) |
| 可变全局 | 5 个 | 0 个 | **0 个**(并由护栏测试锁死) |
| 测试对全局的依赖 | 23 处 | 0 处 | **0 处** |
| `mock.patch.object` 打桩点 | 25 处 | 0 处 | **0 处**(全改注入) |
| 纯逻辑可测性 | 需构造网络桩 | 纯函数直测 | `tests/domain/` 41 项零打桩 |
| 架构违规检测 | 人工 review | CI 自动拦截 | `tests/test_layering.py`,已反向验证有效 |
| 测试总数 | 56 项 | — | **155 项**,全部离线 |

### 与设计的四处偏离(均有理由)

1. **目录用 `paperkit/` 而非 `src/paperkit/`。** 用户已按 flat layout 建好包,
   而这个项目不需要「防止误 import 源码目录」那层保护(它本身就是可直接运行的
   脚本)。改成 `src/` 只会让 `python fetch_papers.py` 失效。

2. **`infra/storage.py` 同时承担 fs 与 registry,未拆成 `fs.py` + `registry.py`。**
   `write_text_atomic` 与 `RegistryStore` 是一对(后者只用前者),合并在一个
   47 行文件里比拆成两个各 25 行更易读。

3. **`log()` 保留 print 实现,未改用标准库 `logging`。** 设计 §5.2 说要换,但
   现有测试断言的是「GBK 控制台不因 ✓ 崩」这一具体行为,换成 logging 后输出
   走 handler、不再经过可被断言的 stdout,反而失去覆盖。日志本身就是给人看的
   进度行,不需要分级/handler/formatter 那一套。

4. **`PaperHTMLParser` 218 行未再拆。** 它是事件驱动的流式状态机,状态在
   `handle_starttag` / `handle_endtag` / `handle_data` 之间共享(`_skip` 栈、
   `_buf`、`_table`)。按行数硬切会把状态机切碎,可读性反而下降。这是
   「≤250 行」目标唯一的例外。

### 一处设计遗漏(实施时补上)

`write_text_atomic` 不在原设计里,是用户在迁移过程中加的,但补得对:翻译缓存
每 20 段落盘一次,而中断正是本项目的高频场景,非原子写会留下半截 JSON 让整篇
进度报废。已在 P0 提交中保留并补充了测试。

### 后续可做(设计 §10 P5)

参考文献整体跳过(`[12]` 无法回溯)、PDF 无断点续传、`vN` 被剥掉导致版本不可
锁定、无 BibTeX 导出、无缓存失效/清理命令。现在有了分层与依赖注入,这些都
比重构前好做。

---

## 附:后续变更(2026-09-14)

### 已完成:`--bilingual all` 跳过已生成

**动因**:`fetch_paper_html` 排在「哪些段落需要翻译」的判断之前,所以即使译文
全部命中缓存,每篇仍要发一次网络请求。库里 23 篇时只浪费 2 次;涨到 200 篇、
190 篇已生成时,一次 `all` 就是 200 次请求,其中 190 次纯属浪费。中断后重跑
也无法真正「接着跑」。

**实现**:

- `services/bilingual.is_generated(entry, settings)` —— 要求登记表有 `bilingual`
  字段**且**文件确实在磁盘上。`services/listing.py` 的 ◈ 改为复用它,消除两处
  口径漂移的风险。
- `build_bilingual(..., force=False)` —— 已生成则提前返回,不联网、不建目录、
  不改登记表。
- CLI:`-f/--force` 原先只作用于下载,现在同样作用于 `--bilingual`;
  `_cmd_bilingual` 先过滤出待生成列表,使 `[i/n]` 进度反映「本次真正要做多少
  篇」,并报告跳过数。

**顺带清理**:删除 `paperkit/storage.py` —— 全项目无人 import 的兼容层
(`infra/cache.py` 引的 `.storage` 是 `infra/storage.py`)。`tests/test_layering.py`
里三处为它开的口子(compat 分层、`storage.py` 特判)一并移除。

**测试**:155 → 162 项。其中 `test_nothing_retranslated_when_cache_is_warm` 必须
补 `force=True` —— 它原本靠「跑第二次」验证缓存语义,加了跳过之后第二次会被提前
拦掉,断言照样通过但覆盖已失效。绿灯掩盖覆盖失效,比红灯更危险。

**踩到的坑**:本机 Git Bash 下 `git rm paperkit/storage.py` 意外删除了整个
`paperkit/` 工作区目录(暂存区只记录了那一个文件,其余 28 个显示为未暂存的
删除)。已用 `git checkout HEAD -- paperkit/` 完整恢复,此后改用
`rm` + `git add -A` 记录删除。**本项目避免使用 `git rm`。**

### 已完成:ruff 接入与 CI 扩矩阵

**发现**:`pyproject.toml` 里 select 了 E/F/W/I/UP/B/C4/SIM 八条规则集,但 CI
从没跑过 ruff——配了不跑等于白配。首次 `ruff check .` 报出 33 个问题(20 个
import 排序、5 个嵌套 with、4 个未使用 import,其余 4 个是个别风格项)。29 个
自动修,4 个手工修——其中一条值得记住:`assertRaises(Exception)` 换成具体的
`FrozenInstanceError`,因为前者连属性名拼错抛出的 `AttributeError` 都会算作
通过,等于这条测试没在测它声称测的东西。

**CI 从 1 格扩到 4 格 + 1 个 job**:`unittest` 跑 ubuntu / windows × Python
3.11 / 3.13(`fail-fast: false`,一个平台挂了也要能看到其他平台的结果);另加
一个 job 装 `.[dev]`、跑 `ruff check .`、用 `papers --help` 与
`python -m paperkit --help` 冒烟两个入口。

加 Windows 不是凑数:项目里有三处平台专属代码(`main()` 的 stdout
reconfigure、`log()` 的 GBK 兜底、`write_text_atomic` 的 `Path.replace` 与
换行符处理),而 Windows 正是实际使用环境。**每一步都先在本地隔离 venv 里
验证通过才写进 YAML**。补测:Python 3.11.15 上 166 项全绿,
`requires-python = ">=3.11"` 属实。

### 一处刻意不做:全库 ruff format

`ruff format .` 会重排 36 个 .py,把 `authors: tuple[str, ...]        # 注释`
这类刻意对齐压成两空格。项目的可读性很大程度靠手工排版,不值得为「标准」
牺牲,因此不做全库重排——格式一致性交给 `ruff check` 的 lint 层即可。

它还有个更危险的副作用:会连 `docs/` 与 README 里的 Python 片段一起重排,
既改掉文档中的示例代码,又掩盖「文档示例与当前实现故意不一致」这类信息。
已在 `pyproject.toml` 里用 `extend-exclude = ["*.md"]` 挡住。

### 已完成:元数据 abs 页面兜底 + 已登记条目回填

**起因**:经代理实测后确认,`export.arxiv.org` 的 429 是 **arXiv 侧的限流**,
与本地网络无关——代理出口是 Oracle 印度的机房 IP,反而限得更狠(直连与走代理
都是 429,只有主站 `arxiv.org` 稳定 200)。也就是说这个 429 等不来、也绕不过去,
原先「等接口恢复再补标题」的计划不成立。

**兜底**:`_metadata_from_abs_page()` 改从 `arxiv.org/abs/{id}` 解析。该页
标题、作者、提交年份三样齐全,恰好就是 `make_filename()` 需要的全部信息,
实测与 API 路径产出**完全一致**。两个易错点已写进测试:标题/作者块里的
`<span class="descriptor">Title:</span>` 必须先整段删掉(只剥标签会留下
「Title:」并原样进文件名);`href` 里的 `&amp;` 要走 `html.unescape`。

失败方向是**安全的**:解析不出标题就返回 `None`,退化成「待补全元数据」,
绝不会产出半成品文件名。成功路径不会多打一次网络(有测试卡住 `call_count`)。

**顺带挖出的真 bug**:`_cmd_add` 里回填逻辑是 `if entry["id"] not in known`
——只有**新**条目才入表,已登记的 id 从不更新。于是「当初限流只存了 id、
后来元数据拿到了」这个场景下,PDF 按正确名字落了盘,登记表却永远停在半成品:
`--list` 一直显示「待补全元数据」,`--all` 每次都要重试一遍。改成对已登记条目
**只补缺失字段**——尤其绝不覆盖已有的 `file`:PDF 已按旧名字落盘,改掉 `file`
就等于指向一个不存在的文件。

**验证**:`2201.11903` 端到端跑通,文件名
`2022 - Wei et al. - Chain-of-Thought Prompting Elicits Reasoning in Large
Language Models [2201.11903].pdf`;重生成对照材料时只有标题那一段是新缓存键,
其余 216 段与 4 张图片全部命中缓存,几秒完成。

**测试**:166 → 177 项(兜底 7 项 + 回填 4 项)。

### 已完成:内联 SVG 插图(漏 7/11 张的根因)

**发现**:用户问「只有四张图片吗」——直觉是对的。2201.11903 实际有 **11 张图**
(14 个面板),工具只抓到 4 张,另外 7 张被**静默丢弃**,而且全程没有任何提示。

**根因**:LaTeXML 把一部分插图渲染成 **内联 `<svg class="ltx_picture">`**,
而不是 `<img>` 或 `<object data>`。解析器的 `_skip_this()` 原本把所有 `<svg>`
整棵子树跳过(为了躲开页头的导航/主题按钮),于是这类图一并没了。

```
F1  <img>            ✓        F2  inline svg   ✗
F3  <object>         ✓        F4  inline svg ×3 ✗
F9  <object>         ✓        F5/F6/F7/F8/F11  ✗
F10 <object>         ✓
```

**修法**:只放行 `class` 含 `ltx_picture` 的 `<svg>`,其余(页面 UI,实测有
`toggle-icon` 等 7 个无 class 的 `role="presentation"` 图标)照旧跳过。标记用
`get_starttag_text()` 逐段拼回,存成 `("svg", "名字\t标记")` 块;
services 层用伪协议 `inline-svg:<名字>` 占位,由 `localize_images` 写成
`assets/<id>/inline/<名字>.svg`。

**为什么用伪协议而不是 `data:` URI**:几十 KB 的 SVG 塞进 Markdown 会让文件
没法读。实测 14 张图只让 md 长了 592 字节(176754 → 177346)。

**踩到的四个坑**(每一个都有测试兜着):

1. **大小写**:`HTMLParser` 把标签名转小写后再给回调,而 SVG 的
   `foreignObject` / `clipPath` 是大小写敏感的。用回调给的 tag 拼结束标签会
   拼出 `</foreignobject>`,**10 个文件全是非法 XML**。改为用栈记住起始标签的
   原始大小写。教训:当时的测试全用的小写标签,一路绿灯——**绿灯掩盖产物损坏,
   比红灯危险**,所以补了「产物必须能当 XML 解析」的断言。
2. **命名空间**:内联 SVG 不写 `xmlns`(嵌在 HTML 里不需要),抽成独立文件后
   缺了它浏览器按未知 XML 处理、渲染成空白。`_ensure_namespace()` 补上。
3. **文本节点转义**:`convert_charrefs=True` 已经把实体解码,直接拼回去会拼出
   非法标记,也会让剥标签逻辑把 `&lt;` 解码出的 `<` 当成真标签吃掉。
4. **`<foreignObject>` 文字全丢**:SVG 被 `<img>` 引用时浏览器进入「安全静态
   模式」,foreignObject 内容一律不渲染——图上的刻度、图例、标题**全部消失**,
   只剩光秃秃的曲线。改为转成原生 `<text>`(`_flatten_foreign_objects`)。
   位置还原要点:foreignObject 不带 x/y,靠祖先 `<g>` 定位,自身带一个垂直翻转
   `matrix(1 0 0 -1 0 T)`(因为框里是 y 向下排版的 HTML),所以**原样保留那个
   transform** 搬到 `<text>` 上让两级翻转抵消(不保留整片文字会倒过来)。
   基线取 `T + 0.6 × 字号`,0.6 是对着原始内联渲染做**像素级扫描**
   (0.45→0.70 步进 0.05)扫出来的,三张图一致。
   另:内层 span 常带 `font-size:90%/80%` 的二次缩放,漏掉文字会整体偏大。

**验证**:不只是跑测试——用 Chrome 无头模式把产物渲染出来,与原始内联渲染
**并排比对 + 像素差**,并逐个校验 221 个 `<text>`、0 个非法文件。

**测试**:177 → 213 项。
### 已完成:内联 SVG 的第二轮(大小写之外还有三层)

第一轮修完只验证了 2201.11903 一篇。补做全库核对时发现**另外还有一篇中招**:

| 论文 | 内联插图 | 解析出的图 | 当时文件里的引用 | 结论 |
|------|---------|-----------|----------------|------|
| 2210.03629 | 0 | 6 | 6 | 不受影响 |
| 2201.11903 | 10 | 14 | 14 | 已修 |
| 2501.12948 | 1 | 21 | 20 | **漏 1 张** |

**核对办法**(不重新生成、只读):直接调 `fetch_paper_html` 抓 HTML,统计
`class="ltx_picture"` 的个数与 `parse_blocks` 出来的 `svg`/`image` 块数,再和
现有 md 里的图引用数比对。**不能只看引用总数**——漏图只会让数字变小,和「本来
就没有这张图」长得一模一样,必须拿到源 HTML 才能判定。

**新暴露的坑**(2501.12948 的那张图,`A2.SS2.p1.pic1`):

1. **栈被空元素堵死**。`<br class="ltx_break">` 是空元素,没有结束标签,
   `HTMLParser` 只回调一次 starttag,于是它永远留在 `_svg_stack` 栈顶,把后面
   所有配对都挡掉。修法:空元素不压栈,并且配对时**从栈顶往下找**而不是只看
   栈顶(LaTeXML 的 `<span>` 也常常不闭合)。
2. **空元素的 HTML 写法在 XML 里非法**。`<br>` 没有结束标签,后面所有标签都会
   被当成它的子节点,整份 `.svg` 报 `mismatched tag`。修法:采集时补成 `<br/>`。
   同理,未闭合元素要在它的父标签前补上隐含的结束标签(`</span></clipPath>`)。
3. **扁平化会静默失效**。`_FOREIGN` 找的是 `</foreignObject>`,而坑 1 让闭合
   标签变成了小写 `</foreignobject>`,正则配不上就**一声不吭地跳过**整块替换,
   留下未闭合标签。修法:正则加 `re.I`,让大小写不匹配变成「被修复」而不是
   「被忽略」。
4. **这张「图」其实是正文**。`foreignObject` 里装的是 7 段共 1729 字的
   **LLM-as-a-judge 提示词模板**。按图形处理会两头不讨好:转 `<text>` 没法折行,
   一行几十上百字符会横向溢出到框外;而 `_fo_plain` 只取第一个 `alttext`,会把
   整块正文压成一个 `\gg`——**内容毁灭**。
   修法:`_fo_is_flow()` 判定为正文图时降级成 `verbatim` 文本块(文档里显示为
   【原文块】),完整、可选中、可翻译。判定要**同时**满足结构信号
   (`ltx_minipage` 或 ≥3 个 `<br>`)和文字量阈值(`MIN_FLOW_CHARS = 200`,
   实测样本 1729 字,8 倍余量)——只看 `<br>` 会把「图例里换了一行」的图表
   误判成正文,那样整张图降级成文本、图形全丢,正是这一轮在修的那类静默损失。
   行内公式取 `<mo>` 里的可见字形(`≫`)而不是 `alttext`(LaTeX 源码 `\gg`)。
   混合插图(既有图形标签又有正文块)不降级,避免丢图形。

**顺带加的一道闸**:`images.is_well_formed()` 在写盘前用 `ElementTree` 校验一次,
不合法就记一条日志。解析器的输入是脏 HTML,与其再产出一批浏览器打不开的 `.svg`
而无人察觉,不如让它在日志里喊一声。

**验证**:

* 2201.11903 重新生成后与原文件 **SHA-256 完全一致**(177346 字节)——改动是
  纯增量,没有动到已经验证过的产物。
* 2501.12948:图引用 20(全本地)+ 提示词模板落入【原文块】,全文 0 处 `\gg`。
* 全库 36 个 `.svg`(含下载的远程矢量图)全部合法,0 个非法;221 个 `<text>`。
* 顺手删掉第一次生成留下的那个非法孤儿文件 `inline/A2.SS2.p1.pic1.svg`。

**测试**:213 → 227 项(大小写配对 7 项 + 正文图判定 7 项)。

**教训(和第一轮同源)**:两轮的根因都是「**fixture 比真实数据干净**」。第一轮
的 fixture 清一色小写标签,这一轮的 fixture 清一色良好闭合、没有空元素。补的
断言因此都指向同一件事:**产物必须能当 XML 解析**,而不是「某个字符串出现在
某个位置」。
