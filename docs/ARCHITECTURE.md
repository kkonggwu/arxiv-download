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

| 项 | 为何重构后才做 |
|---|---|
| 断点续传 / Range 下载 | 需要 `HttpClient` 支持自定义 header |
| `--bilingual all` 跳过已生成 | 需要 `BilingualService` 暴露「是否已完成」查询 |
| 版本号固定（不剥 `vN`） | 需要 `PaperEntry` 增加 `version` 字段 |
| 引用编号可跳转 | 需要解析阶段保留 `ltx_bibliograph` 结构 |
| 并发下载（线程池） | 需要 `Settings` 无共享可变状态 |

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
