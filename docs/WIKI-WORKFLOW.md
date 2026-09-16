# 论文阅读工作流：paperkit × LLM Wiki

> 本文描述「下载论文 → 中英对照精读 → 手动进 LLM Wiki 建知识网络」这条
> 三阶段流水线，以及两套工具之间如何衔接。核心原则：**paperkit 干机械活，
> 你在 LLM Wiki 里干需要判断的活（关系创建）**——这正是 LLM Wiki 自身
> 「Human curates, LLM maintains」的立场。

---

## 1. 定位：两套工具是同一流水线的上下两层

| | paperkit | LLM Wiki（`wiki/`） |
|---|---|---|
| 干什么 | 下载 PDF、逐段生成中英对照精读稿 | 把文档蒸馏成交叉链接的知识库 |
| 粒度 | 单篇、逐段、全文 | 跨篇、抽取、归纳（实体/概念/来源页） |
| 产物 | `papers/<分类>/*.pdf` + `papers/双语/<分类>/<id> 中英对照.md` | `wiki/wiki/{entities,concepts,sources}/*.md` + 知识图谱 |
| 元数据 | `papers.json`（唯一事实源） | 每页 YAML frontmatter |
| 谁在操作 | 脚本 | 人 + LLM（桌面 App） |

一句话：**paperkit 负责「拿到材料 + 精读单篇」，LLM Wiki 负责「融会贯通成
知识网络」。** 两者不抢同一份 PDF、不抢同一份元数据，只在「交接点」碰头。

---

## 2. 三阶段流水线

```
┌─ ① 收集 + 分类（paperkit，全自动）───────────────────────────┐
│   papers <arXiv id|链接> --category <分类>                    │
│     → papers/<分类>/<年份 - 作者 - 标题 [id].pdf>              │
│     → papers.json 登记 metadata（title / authors / year）     │
└──────────────────────────────────────────────────────────────┘
                          │
┌─ ② 翻译双语（paperkit，全自动）───────────────────────────────┐
│   papers --bilingual <id>                                    │
│     → papers/双语/<分类>/<id> 中英对照.md   ← 你自己的精读文件夹│
└──────────────────────────────────────────────────────────────┘
                          │
┌─ ③ 进知识库建关系（人工 + LLM Wiki）──────────────────────────┐
│   a. papers --list       看第三列 ⬡ → 找出「还没进 wiki」的论文 │
│   b. 手动把该篇 PDF 复制到 wiki/raw/sources/                   │
│   c. 在 LLM Wiki 里 ingest → LLM 建 source 页 + 实体/概念页 + 关系│
│   d. papers --wiki-link <id> wiki/wiki/sources/<slug>.md  回填 │
└──────────────────────────────────────────────────────────────┘
```

③ 的四步里，只有 a 和 d 需要工具（跟踪「哪篇还没进 wiki」），b、c 完全
留给你手动做。这正是「人工把关」的边界：**LLM Wiki 不做「自动抓论文进来」，
paperkit 不做「自动建关系」**。

---

## 3. 目录布局与职责边界

```
06.论文/
├── papers.json                       # ① 写，元数据唯一事实源（含 wiki 字段）
├── papers/<分类>/*.pdf               # ① 写，PDF 唯一落盘处
├── papers/双语/<分类>/<id> 中英对照.md  # ② 写，精读稿
└── wiki/                             # ③ 写，LLM Wiki 的知识库（项目根）
    ├── purpose.md  schema.md         #    知识库的目标与规则
    ├── raw/sources/*.pdf             #    你手动复制进来的 PDF（raw，不可变）
    ├── wiki/                         #    LLM Wiki 的 vault
    │   ├── index.md  log.md  overview.md
    │   ├── sources/  entities/  concepts/  ...
    ├── .llm-wiki/                    #    应用状态（不入库）
    ├── .obsidian/                    #    Obsidian 配置（不入库）
    └── agent-workspace/              #    代理工作区与备份（不入库）
```

**边界铁律**：paperkit 只碰 `papers/` 与 `papers.json`；LLM Wiki 只碰 `wiki/`。
中间「复制 PDF 进 raw/sources」这一步手动动作，就是两条流水线的交接点。

---

## 4. 交接契约：papers.json 的 `wiki` 字段

这是唯一把两套东西连起来的数据。每篇论文的登记条目可以带一个 `wiki` 字段：

```json
{
  "id": "1706.03762",
  "category": "经典",
  "title": "Attention Is All You Need",
  "file": "2017 - Vaswani et al. - Attention Is All You Need [1706.03762].pdf",
  "wiki": "wiki/wiki/sources/vaswani-2017-attention-is-all-you-need.md"
}
```

- **缺省为空** = 该篇还没进 wiki（`--list` 的 ⬡ 列空白）。
- **有值** = 指向该论文在 LLM Wiki 里的 source 页（相对项目根的路径）。
- 注意路径有两层 `wiki/wiki/`：外层 `wiki/` 是 LLM Wiki 的项目根，内层
  `wiki/` 是它内部的 vault，source 页在 `wiki/wiki/sources/` 下。

`--list` 的 ⬡ 沿用 `✓` / `◈` 的同一口径——**既看字段、也看磁盘**：字段有值
但 source 页文件被手工删了，⬡ 就不亮，避免谎报。

---

## 5. 命令

```bash
# 找出还没进 wiki 的论文（第三列 ⬡ 为空白的那些）
python fetch_papers.py --list

# 手动在 LLM Wiki 里 ingest 完一篇后，回填标记
python fetch_papers.py --wiki-link 1706.03762 \
    wiki/wiki/sources/vaswani-2017-attention-is-all-you-need.md
```

`--list` 每行的三个标记：

| 标记 | 含义 | 查什么 |
|---|---|---|
| `✓` | PDF 已落盘 | `papers/<分类>/` 下文件存在 |
| `◈` | 中英对照已生成 | `papers/双语/` 下文件存在 |
| `⬡` | 已进 LLM Wiki | `wiki/wiki/sources/` 下 source 页存在 |

三个标记互相独立：元数据没补全 ≠ 没生成对照稿 ≠ 没进 wiki。

---

## 6. 手动步骤（③）详解

1. `papers --list` 扫一遍，`⬡` 列空白的论文就是「待进 wiki」的候选。
2. 挑一篇，把 `papers/<分类>/<文件名>.pdf` **复制**（不是移动，更不是硬链接
   到别处删原文件）到 `wiki/raw/sources/`。
   - 用原始 PDF，不用双语 md：LLM Wiki 自带 pdf-extract，且「raw 不可变」
     原则要求喂进去的是原始文档；双语 md 是你自己精读用的，两者各司其职。
3. 打开 LLM Wiki App，选中这个项目 → 触发 ingest。LLM 会：
   - 生成 source 页（带 authors / year / url / venue 的 frontmatter）；
   - 抽取实体页、概念页，并建立 `[[wikilink]]` 交叉引用（**关系创建**）；
   - 更新 `index.md` / `log.md` / `overview.md`。
4. 回到 paperkit，跑 `--wiki-link <id> <source 页路径>` 回填标记。之后
   `--list` 里该篇的 ⬡ 亮起，表示「已链接」。

> 想一次性把某个分类都喂进去？重复第 2–4 步即可。刻意不做「自动复制 PDF
> 进 wiki」的命令——进不进知识库是你要做的判断，脚本不该替你决定。

---

## 7. 版本管理约定

`.gitignore` 已配置：只入库知识本体，其余一律忽略。

| 路径 | 处理 | 理由 |
|---|---|---|
| `wiki/wiki/**/*.md`、`purpose.md`、`schema.md` | ✅ 入库 | 这是知识本体，是成果 |
| `papers/`、`wiki/raw/sources/` | ❌ 忽略 | 可重建 / 重复的 PDF |
| `wiki/.llm-wiki/`、`wiki/.obsidian/` | ❌ 忽略 | 应用状态、本地编辑器配置 |
| `wiki/agent-workspace/` | ❌ 忽略 | 代理工作区与备份（含提取图片） |

---

## 8. 明确不做（YAGNI）

- ❌ **不自动复制 PDF 进 wiki**：进不进知识库是人工判断，脚本不越界。
- ❌ **不做硬链接/符号链接**：LLM Wiki 的 raw 目录要的是不可变副本，硬链接
  会让「删一份另一份也没了」的语义变隐晦；复制一份虽占点磁盘，但边界清晰。
- ❌ **不把双语 md 当 wiki 输入**：双语稿是生成物，重跑 `--force` 会变，会
  打乱 LLM Wiki 的 SHA256 增量缓存；raw 必须是原始 PDF。
- ❌ **不试图「调用」LLM Wiki**：它是独立桌面 App，paperkit 与它的边界就是
  磁盘上的 Markdown/JSON 文件，不是进程间通信。
- ❌ **不为此破坏零依赖**：新增的 `--wiki-link` / ⬡ 跟踪只用了 stdlib
  （`pathlib` / `json` / 已有的 `RegistryStore`），`pyproject.toml` 的
  `dependencies = []` 不变。
