# 论文库 & 下载脚手架

从 arXiv 批量下载论文 PDF，并把论文 HTML 版逐段翻译成**中英对照 Markdown**
（英文段在上、中文引用块在下），方便「先裸读英文、再对照校对」。

运行时**零第三方依赖**，只用 Python 标准库——任何装了 Python 3.11+ 的机器
都能直接跑，不需要 pip 装任何东西。

## 文件结构

```
06.论文/
├── fetch_papers.py            # 兼容入口(转发到 paperkit.cli)
├── pyproject.toml             # 打包配置(零运行时依赖 + papers 命令)
├── paperkit/                  # 实现,按层组织
│   ├── cli/                   #   命令行边界:参数、Settings 组装、退出码
│   ├── services/              #   应用层:download / bilingual / images / listing / registry
│   ├── domain/                #   领域层:纯规则与纯渲染,零副作用
│   │   ├── arxiv_id.py        #     arXiv id 解析(新旧两代)
│   │   ├── naming.py          #     文件名生成
│   │   ├── markdown.py        #     表格/代码块/公式/标题级别渲染
│   │   ├── glossary.py        #     术语表与机翻缩写纠错
│   │   └── html_parser.py     #     LaTeXML HTML → 区块序列
│   ├── infra/                 #   基础设施:http / storage / cache / translate / logging
│   ├── config.py              #   唯一的 frozen Settings
│   └── errors.py              #   异常层级
├── tests/                     # 回归测试(155 项,全程离线)
│   ├── domain/  infra/  services/
│   └── test_layering.py       #   架构护栏:依赖方向不对 CI 就红
├── docs/
│   ├── ARCHITECTURE.md        # 分层设计、数据契约、迁移路线
│   └── REFACTOR-REVIEW.md     # 重构验收评估
├── papers/                    # 下载的 PDF 与生成物(已 gitignore)
│   ├── 经典/ 推理前沿/ Agent/ PL与AI交叉/
│   └── 双语/                   # --bilingual 生成的中英对照 Markdown(同分类子目录)
│       ├── .cache/            # 翻译缓存,按后端分文件
│       └── assets/<id>/       # 从论文里抓下来的插图,按原路径存
└── README.md
```

`papers/` 约 70MB，可由脚本重建，因此不纳入版本管理；`papers.json` 入库。

## 安装（可选）

不安装也能用——直接 `python fetch_papers.py ...` 即可。装了会多一个
`papers` 命令，并且能在任意目录调用：

```bash
pip install -e .          # 只装本体,零依赖
pip install -e ".[dev]"   # 额外装 pytest / ruff
```

## 常用命令

```bash
# 下载登记表中所有未落盘的论文(自动跳过已存在的)
python fetch_papers.py --all --proxy http://127.0.0.1:7897

# 生成中英对照阅读材料(单篇 / 全部;已生成的自动跳过)
python fetch_papers.py --bilingual 2210.03629 --proxy http://127.0.0.1:7897
python fetch_papers.py --bilingual all --proxy http://127.0.0.1:7897

# 添加并下载新论文(支持 arXiv id 或链接)
python fetch_papers.py 2501.12948 --category 推理前沿
python fetch_papers.py https://arxiv.org/abs/2405.15793 --category Agent

# 查看清单与下载状态
python fetch_papers.py --list

# 强制重新下载 PDF / 重新生成中英对照(对 --all 与 --bilingual 都生效)
python fetch_papers.py --all --force --proxy http://127.0.0.1:7897
python fetch_papers.py --bilingual all --force

# 只补图片链接、不下载插图(离线场景)
python fetch_papers.py --bilingual 2501.12948 --no-images
```

装了包之后，上面所有 `python fetch_papers.py` 都可以换成 `papers`；
`python -m paperkit` 同样等价。

### 重复运行与跳过

`--bilingual` 对**已生成**的论文默认跳过。判断依据是两个条件同时成立：
登记表里有 `bilingual` 字段，**且**文件确实在磁盘上——`--list` 的 ◈ 用的是
同一口径。所以手工删掉某篇的 md 之后再跑，它会被重新生成；想整体重做则加
`--force`。

跳过发生在联网之前，重跑 `--bilingual all` 不会为已完成的论文重复抓取 HTML。
库越大越省事，中断之后重跑也等同于「接着跑」。

### 退出码

| 码 | 含义 |
|---|---|
| 0 | 全部成功（或没有需要处理的内容） |
| 1 | 全部失败 |
| 2 | 部分失败（批量模式下单篇失败不拖垮整批） |
| 3 | 参数或配置错误 |

## 翻译后端

`--bilingual` 默认用 `google`（免 Key 的免费网页接口）。需要更稳定的质量或
额度时切到 `openai`，可指向任何 OpenAI 兼容服务（OpenAI / DeepSeek / vLLM /
Ollama 等）：

```bash
# 用 DeepSeek 翻译
export TRANSLATE_API_KEY=sk-xxx
python fetch_papers.py --bilingual 2501.12948 \
    --translator openai \
    --translate-base-url https://api.deepseek.com/v1 \
    --translate-model deepseek-chat
```

对应环境变量：`TRANSLATE_BACKEND`、`TRANSLATE_BASE_URL`、`TRANSLATE_MODEL`、
`TRANSLATE_API_KEY`（命令行参数优先于环境变量）。不同后端各用一份缓存
（`{id}.json` 给 google，`{id}.openai.json` 给 openai），换后端会重新翻译。

新增一个后端只需在 `paperkit/infra/translate/` 写一个满足 `Translator` 协议
的类，再在 `_BUILDERS` 里加一行。

## 开发

```bash
# 跑回归测试(仅标准库,全程离线,不需要网络)
python -m unittest discover -s tests -t .

# 只跑某一层
python -m unittest discover -s tests/domain -t .

# 代码风格(需先 pip install -e ".[dev]")
ruff check .
ruff format .
```

测试全程不联网、不改真实数据：翻译走 `FakeTranslator` 注入，产物路径走
`Settings(base_dir=临时目录)`。`tests/test_layering.py` 会用 AST 检查依赖
方向——`domain` 层若 import 了 `infra`、或调用了 `open()`/`read_text()`，
测试直接失败。

CI（`.github/workflows/tests.yml`）做两件事：`unittest` 覆盖 ubuntu / windows
× Python 3.11 / 3.13 的四格矩阵；另一个 job 装 `.[dev]`、跑 `ruff check .`、
再用 `papers --help` 与 `python -m paperkit --help` 冒烟两个入口。提交前把上面
两条命令在本地跑一遍即可。

## 说明

- **代理**：arXiv 直连常被阻断。`--proxy http://127.0.0.1:7897` 走 Clash Verge 的混合端口
  （端口以本机 Clash 配置为准），或设置环境变量 `HTTPS_PROXY`。
  Clash Verge GUI 关闭后核心可能停掉，重新打开 GUI 即可。
- **文件名**：`年份 - 第一作者 et al. - 标题 [arXiv id].pdf`，元数据来自 arXiv Atom API。
- **限流**：对 arXiv 的请求间隔 3 秒；元数据接口（`export.arxiv.org`）另有更严的
  速率限制，实测会持续返回 429，此时日志会明确提示「稍后重试即可」——PDF 与 HTML
  不受影响，元数据等接口恢复后 `--all` 会自动补全。
- **中英对照**（`--bilingual`）：抓取论文 HTML 版（arXiv 原生，老论文自动退回 ar5iv），
  逐段翻译后生成 Markdown：英文段在上、中文对照在下（引用块），公式保留为 `$...$` LaTeX，
  图注带【图注】标记，常见章节名（Abstract 等）用固定译法，标题层级保留为 h2–h5。
  翻译结果缓存在 `papers/双语/.cache/`，重跑只补缺；`--list` 中 `◈` 表示已生成，
  已生成的论文在 `--bilingual all` 时会自动跳过（`--force` 可重建）。
  建议配三遍法使用：第一遍只读英文，第二遍对照校对，第三遍用英文写 3 句总结。
- **表格与原文块**：论文里的表格会转成 Markdown 表并加 `【表格】` 标记；单列的
  `<table>`（prompt 模板、对话记录、代码清单）转成代码块并加 `【原文块】` 标记。
  两者都按原文保留、不参与翻译——里面多是数字与模型名，逐格机翻既容易破坏结构，
  对阅读也没帮助。已知取舍：跨列/跨行单元格（colspan/rowspan）不展开，多行表头
  会退化为「首行做表头」，因此这类表的列对齐可能与原表不一致，但文字内容不丢；
  行间公式的编号 `(1)` 不保留。
- **图片**：论文插图会下载到 `papers/双语/assets/<id>/`（保留原目录层级），正文用
  `../assets/...` 相对路径引用，断网也能看图。已下载过的直接复用，不重复请求；
  单张失败时退回 arXiv 绝对链接，不会因为一张图失败就中断整篇。
  注意 arXiv/ar5iv 用 LaTeXML 渲染，大多数插图是 `<object type="image/svg+xml">`
  而非 `<img>`，只认 `<img src>` 会漏掉绝大多数图（实测 DeepSeek-R1 正文 20 张图里
  有 17 张是 `<object>`）。两篇实测体积约 1.5–3.4MB。
- **翻译失败**：只有成功的译文才写进缓存。失败的段落本次渲染为 `⚠`，重跑会自动
  重试（早期版本会把失败写进缓存，导致该段永远不再重试）。
- **元数据失败**：取不到就只登记 `id` + 分类、**不写占位文件名**，下次 `--all`
  自动补全。若写成 `- Unknown - <id> [<id>].pdf`，该条目会被永久钉死在错名字上。
- 新论文直接加进 `papers.json`（只需 `id` 和 `category`），`--all` 时会自动补全元数据。
