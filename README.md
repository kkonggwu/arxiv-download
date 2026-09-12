# 论文库 & 下载脚手架

## 文件结构

```
06.论文/
├── fetch_papers.py            # 下载 + 中英对照脚手架(仅依赖 Python 标准库)
├── papers.json                # 论文登记表(id + 分类;下载后自动补全元数据)
├── tests/                     # 回归测试(unittest,不联网)
├── papers/                    # 下载的 PDF,按分类分目录(已 gitignore)
│   ├── 经典/
│   ├── 推理前沿/
│   ├── Agent/
│   ├── PL与AI交叉/
│   └── 双语/                   # --bilingual 生成的中英对照 Markdown(同分类子目录)
│                              # .cache/ 内为翻译缓存,按后端分文件
└── README.md
```

`papers/` 约 70MB，可由脚本重建，因此不纳入版本管理；`papers.json` 入库。

## 常用命令

```bash
# 下载登记表中所有未落盘的论文(自动跳过已存在的)
python fetch_papers.py --all --proxy http://127.0.0.1:7897

# 生成中英对照阅读材料(单篇 / 全部)
python fetch_papers.py --bilingual 2210.03629 --proxy http://127.0.0.1:7897
python fetch_papers.py --bilingual all --proxy http://127.0.0.1:7897

# 添加并下载新论文(支持 arXiv id 或链接)
python fetch_papers.py 2501.12948 --category 推理前沿
python fetch_papers.py https://arxiv.org/abs/2405.15793 --category Agent

# 查看清单与下载状态
python fetch_papers.py --list

# 强制重新下载
python fetch_papers.py --all --force --proxy http://127.0.0.1:7897

# 跑回归测试
python -m unittest discover -s tests -v
```

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

## 说明

- **代理**：arXiv 直连常被阻断。`--proxy http://127.0.0.1:7897` 走 Clash Verge 的混合端口
  （端口以本机 Clash 配置为准），或设置环境变量 `HTTPS_PROXY`。
  Clash Verge GUI 关闭后核心可能停掉，重新打开 GUI 即可。
- **文件名**：`年份 - 第一作者 et al. - 标题 [arXiv id].pdf`，元数据来自 arXiv Atom API。
- **限流**：对 arXiv 的请求间隔 3 秒，23 篇约需 2–3 分钟。
- **中英对照**（`--bilingual`）：抓取论文 HTML 版（arXiv 原生，老论文自动退回 ar5iv），
  逐段翻译后生成 Markdown：英文段在上、中文对照在下（引用块），公式保留为 `$...$` LaTeX，
  图注带【图注】标记，常见章节名（Abstract 等）用固定译法。
  翻译结果缓存在 `papers/双语/.cache/`，重跑只补缺；`--list` 中 `◈` 表示已生成。
  建议配三遍法使用：第一遍只读英文，第二遍对照校对，第三遍用英文写 3 句总结。
- **表格与原文块**：论文里的表格会转成 Markdown 表并加 `【表格】` 标记；单列的
  `<table>`（prompt 模板、对话记录、代码清单）转成代码块并加 `【原文块】` 标记。
  两者都按原文保留、不参与翻译——里面多是数字与模型名，逐格机翻既容易破坏结构，
  对阅读也没帮助。已知取舍：跨列/跨行单元格（colspan/rowspan）不展开，多行表头
  会退化为「首行做表头」，因此这类表的列对齐可能与原表不一致，但文字内容不丢；
  行间公式的编号 `(1)` 不保留。
- **翻译失败**：只有成功的译文才写进缓存。失败的段落本次渲染为 `⚠`，重跑会自动
  重试（早期版本会把失败写进缓存，导致该段永远不再重试）。
- 新论文直接加进 `papers.json`（只需 `id` 和 `category`），`--all` 时会自动补全元数据。
