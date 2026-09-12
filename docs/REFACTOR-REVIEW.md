# 重构验收评估

> 评估对象：工作区当前未提交的重构改动（`M fetch_papers.py`、`M tests/test_fetch_papers.py`、`?? paperkit/`）
> 评估基准：`docs/ARCHITECTURE.md`（模块化重构设计方案）
> 评估时间：2026-09-12
> 结论：**功能完好，但架构目标 0/7 达成**——这是一次「搬迁 + 外壳」重构，不是分层重构。

---

## 1. 一句话结论

代码搬进了包、入口做了兼容、测试全绿（56/56），还顺手加了三个设计方案里没提的真实改进；
但**单文件上帝模块的问题原样保留**：`paperkit/core.py` 1248 行，比原来的 `fetch_papers.py`
（1218 行）**还多 30 行**。设计方案 §13 列的 7 项收益，一项都没拿到。

---

## 2. 实际发生了什么

| # | 动作 | 性质 |
|---|---|---|
| 1 | `fetch_papers.py` → `paperkit/core.py`（整体平移，改 `BASE` 为 `parent.parent`） | 搬迁 |
| 2 | `fetch_papers.py` 变成 13 行兼容壳，用 `sys.modules[__name__] = core` 把自身替换掉 | 兼容层 |
| 3 | 新增 `paperkit/config.py`（`Settings`，30 行） | 新增 |
| 4 | 新增 `paperkit/domain.py`（3 个纯函数，35 行） | 部分抽取 |
| 5 | 新增 3 个测试（`TestLogging` / `TestAtomicWrites` / `TestSettings`） | 新增 |
| 6 | 新增 `write_text_atomic()`，登记表与缓存的写入改为原子替换 | **真实改进** |
| 7 | `log()` 加 GBK 兜底，控制台编码不支持 `✓` 时降级而非崩溃 | **真实改进** |

测试从 53 项增至 **56 项，全部通过**（离线）。`--list`、`--help`、`--bilingual` 均可用。
**功能层面无回归。**

---

## 3. 与设计方案的逐项对照

### 3.1 迁移阶段（ARCHITECTURE.md §10）

| 阶段 | 计划内容 | 实际 | 判定 |
|---|---|---|---|
| **P0** | 建包骨架 + `Settings` 替代全局 | 骨架有、`Settings` 有，但字段只有 5 个（设计要 14 个），且**建完立刻抄回全局** | 🟡 半成品 |
| **P1** | 抽离 `infra/`（http、registry、cache、translate、logging） | 无 `infra/` 目录 | ❌ 未做 |
| **P2** | 抽离 `domain/`（arxiv_id、naming、markdown、html_parser、glossary、models） | 只抽了 3 个纯函数（35 行）；且**旧定义没删**（见 §5.1） | 🟡 12% |
| **P3** | 抽离 `services/` 与 `cli/` | 无 `services/`、无 `cli/`；只是把文件挪了位置 | ❌ 未做 |
| **P4** | `test_layering.py` + `pyproject.toml` + CI | 三项全无 | ❌ 未做 |

### 3.2 收益预估（ARCHITECTURE.md §13）

| 维度 | 重构前 | 设计目标 | **实测现状** | 判定 |
|---|---|---|---|---|
| 最大文件 | 1218 行 | ≤ 250 行 | **1248 行**（`core.py`） | ❌ 反而变大 |
| 最大函数 | 218 行 | ≤ 120 行 | **218 行**（`PaperHTMLParser`，未动） | ❌ |
| 可变全局 | 5 个 | 0 个 | **5 个**（靠 1 处 `global` 改写） | ❌ |
| 测试对全局的依赖 | 23 处 | 0 处 | **23 处**（逐字未变） | ❌ |
| `mock.patch.object` 总数 | 24 处 | 0 处 | **25 处** | ❌ 反而 +1 |
| 新增后端成本 | 改 5 处 + 加全局 | 加 1 文件 + 注册 1 行 | **未变**（仍要动全局） | ❌ |
| 纯逻辑可测性 | 需构造网络桩 | 纯函数直测 | 仅 3 个函数可直测 | ❌ |
| 架构违规检测 | 人工 review | CI 自动拦截 | **无**（无 `test_layering.py`） | ❌ |

**7 项全部未达成。**

---

## 4. 值得肯定的三个改动

### 4.1 `write_text_atomic()` —— 设计里漏掉的真问题

```python
def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()
```

原来的 `cache_file.write_text(...)` 是**非原子**写。翻译缓存每 20 段落盘一次，而
「Ctrl-C / 断网 / 限流卡死」正是这个项目的高频中断场景——一旦在写入瞬间被打断，
缓存文件会变成半截 JSON，下次 `json.loads` 直接抛异常，**整篇已翻好的进度全废**。
`tmp.replace()` 在 Windows 上走 `os.replace`，是原子的。这个改进有实际价值，
设计方案里确实没考虑到。

### 4.2 `log()` 的编码兜底

```python
try:
    print(msg, flush=True)
except UnicodeEncodeError:
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    text = msg.encode(encoding, errors="replace").decode(encoding)
    stream.write(text + "\n")
    stream.flush()
```

原来 `sys.stdout.reconfigure(encoding="utf-8")` 只在 `main()` 里做。测试或其它代码
**直接调用业务函数**（不经 `main()`）时，Windows 控制台的 GBK 会让 `print("✓ ...")`
直接抛 `UnicodeEncodeError` 把任务打断。兜底逻辑正确：`TextIOWrapper.write()`
会先编码整串再写，异常发生在写入前，所以不会产生半行输出。

### 4.3 兼容壳的设计

```python
if __name__ != "__main__":
    sys.modules[__name__] = core
```

这一步是**为了让现有 25 处 `mock.patch.object(fp, "http_get")` 不炸**——因为
`import fetch_papers` 拿到的就是 `paperkit.core` 模块对象本身，打桩打在同一个对象上。
在「先搬家、后分层」的迁移策略下，这个手法是对的。已验证：
`fetch_papers is paperkit.core → True`。

---

## 5. 新引入的风险（按严重度）

### 5.1 🔴 重复定义 + 静默遮蔽 —— 建议立刻修

`core.py` 里 `parse_arxiv_id`（154-169）、`sanitize`（211-219）、`make_filename`（222-235）
**仍然保留着原定义**，而文件末尾又做了一次覆盖赋值：

```python
# core.py 第 1240-1244 行
parse_arxiv_id = domain.parse_arxiv_id
sanitize = domain.sanitize
make_filename = domain.make_filename
```

运行期实测：三个名字全部指向 `paperkit.domain`，`core.py` 里的那 39 行是**死代码**。

**为什么危险**：两份实现目前逻辑等价（只差 docstring），但**没有任何测试或工具会告诉你
它们已经分叉**。将来有人（包括你自己）在 `core.py` 里改了 `make_filename` 的截断逻辑，
测试全绿、功能没变——因为改动根本没被执行。这是「两处真相」最典型的坑。

**修法**：删掉 `core.py` 第 154-169、211-219、222-235 行，只保留末尾的再导出。
删完 `core.py` 减 39 行，`import unicodedata`（第 45 行，仅被死代码使用）也可以一并移除。

### 5.2 🟠 `Settings` 的不可变性形同虚设

```python
settings = Settings.from_values(...)   # frozen=True
PROXY = settings.proxy                  # 立刻抄进可变全局
TRANSLATE_BACKEND = settings.translate_backend
OPENAI_BASE_URL = settings.openai_base_url
OPENAI_MODEL = settings.openai_model
TRANSLATE_API_KEY = settings.translate_api_key
```

`frozen=True` 保证的是「`settings` 这个对象不可改」，但字段一被抄进模块全局，
这个保证就完全失效了。**净效果是多了 6 行代码，收益为零**：
- 同进程内仍然无法用两种后端翻译（`translate_one` 读的是全局）
- 测试仍然必须改全局再跑
- `config.py` 里也没有 `base_dir` / `registry_path` / `cache_dir`，路径依然是模块级常量

真正要做的是把 `Settings` 作为参数传进 `translate_one()` / `http_get()` / `build_bilingual()`，
而不是在 `main()` 里「翻译」成全局。

### 5.3 🟠 `core.py` 仍是全能上帝模块，且依赖方向无约束

它同时 import `config` 和 `domain`（说明它是「上层」），却自己干着 HTTP、HTML 解析、
Markdown 渲染、用例编排、CLI 参数解析这五件事。分层没有落地，因此
ARCHITECTURE.md §6 的依赖矩阵**无从校验**——`test_layering.py` 也就不可能写出来。

### 5.4 🟡 包无法安装，也无法从项目外导入

```
$ cd /tmp && python -c "import paperkit"
ModuleNotFoundError: No module named 'paperkit'
```

没有 `pyproject.toml`，`paperkit` 只是一个「恰好放在项目根目录的文件夹」，不是可安装的包。
连带的两个小问题：

- `python -m paperkit` → `No module named paperkit.__main__`（无 `__main__.py`）
- `python paperkit/core.py` → `ImportError: attempted relative import with no known parent package`
  （`core.py` 用了 `from .config import Settings`，只能被导入、不能直接运行）

现在唯一的运行方式仍是 `python fetch_papers.py`，且必须 cwd 在项目根目录。

### 5.5 🟡 README 未同步

`README.md` 的文件结构段仍写着：

```
├── fetch_papers.py            # 下载 + 中英对照脚手架(仅依赖 Python 标准库)
```

没有提到 `paperkit/`。新人（或三个月后的你）会以为实现还在 `fetch_papers.py` 里。

---

## 6. 项目当前状态快照

```
D:\Project\06.论文\
├── fetch_papers.py          13 行   兼容壳（sys.modules 替换）
├── paperkit/
│   ├── __init__.py           5 行   导出 core
│   ├── config.py            30 行   Settings（5 字段，被降级为全局中转）
│   ├── domain.py            35 行   3 个纯函数（无 docstring）
│   └── core.py            1248 行   ← 上帝模块（含 39 行死代码）
├── tests/test_fetch_papers.py  582 行   56 项测试，全绿
├── docs/ARCHITECTURE.md            设计方案（未执行）
├── papers.json / papers/ / README.md
└── 缺失：pyproject.toml、tests/test_layering.py、paperkit/{infra,services,cli,errors.py}
```

**git 状态**：重构**尚未提交**（3 处未暂存改动）。设计方案要求「每阶段独立提交」，
目前 P0/P1/P2 混在一个未提交的工作区里，回退粒度丢失。

**功能健康度**：✅ 无回归。56 项测试通过，CLI 三种模式可用，缓存/登记表路径正确
（`BASE` 从 `parent` 改为 `parent.parent` 是对的，已用 `--list` 实测验证）。

---

## 7. 建议的下一步（最小动作 → 完整落地）

### 立刻做（10 分钟，纯删除，零风险）

1. 删 `core.py` 第 154-169、211-219、222-235 行（39 行死代码），顺手删第 45 行 `import unicodedata`
2. 补 `paperkit/domain.py` 的 docstring（从被删的 `core.py` 版本搬过来，别浪费）
3. 跑测试确认仍 56 项全绿
4. 按阶段提交：`refactor(P0): 建包骨架与 Settings` + `refactor(P2): 抽出 3 个纯领域函数`

### 接着做（真正的分层，按设计 §10 推进）

5. **P1**：抽 `infra/http.py`、`infra/registry.py`、`infra/cache.py`、`infra/translate/`，
   引入 `Transport` / `Translator` Protocol
6. **P2**：把 `PaperHTMLParser`（218 行）拆到 `domain/html_parser.py`，
   `render_table` 等拆到 `domain/markdown.py`
7. **P3**：`services/bilingual.py` + `cli/main.py`，让 `core.py` 彻底消失
8. **P4**：`pyproject.toml` + `tests/test_layering.py` + CI

### 关键提醒

**当前这次重构最大的价值是「兼容壳 + 原子写」，最大的成本是「多了一个 1248 行的文件
和一个 39 行的死代码陷阱」。** 如果打算继续做分层，建议先做上面「立刻做」的 4 步，
把工作区清干净再进 P1——否则 `core.py` 会一直是个「既想删又不敢删」的中间态。
