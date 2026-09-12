# 论文库 & 下载脚手架

## 文件结构

```
06.论文/
├── fetch_papers.py   # 下载脚手架(仅依赖 Python 标准库)
├── papers.json       # 论文登记表(id + 分类;下载后自动补全元数据)
└── papers/           # 下载的 PDF,按分类分目录
    ├── 经典/
    ├── 推理前沿/
    ├── Agent/
    ├── PL与AI交叉/
    └── 双语/          # --bilingual 生成的中英对照 Markdown(同分类子目录)
                      # .cache/ 内为翻译缓存,删除后会重新翻译
```

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
```

## 说明

- **代理**:arXiv 直连常被阻断。`--proxy http://127.0.0.1:7897` 走 Clash Verge 的混合端口
  (端口以 `D:\Project\06.论文` 同级的 Clash 配置为准),或设置环境变量 `HTTPS_PROXY`。
  Clash Verge GUI 关闭后核心可能停掉,重新打开 GUI 即可。
- **文件名**:`年份 - 第一作者 et al. - 标题 [arXiv id].pdf`,元数据来自 arXiv Atom API。
- **限流**:对 arXiv 的请求间隔 3 秒,23 篇约需 2–3 分钟。
- **中英对照**(`--bilingual`):抓取论文 HTML 版(arXiv 原生,老论文自动退回 ar5iv),
  逐段翻译后生成 Markdown:英文段在上、中文对照在下,公式保留为 `$...$` LaTeX,
  图注带【图注】标记,常见章节名(Abstract 等)用固定译法。
  翻译结果缓存在 `papers/双语/.cache/`,重跑只补缺;`--list` 中 `◈` 表示已生成。
  建议配三遍法使用:第一遍只读英文,第二遍对照校对,第三遍用英文写 3 句总结。
- 新论文直接加进 `papers.json`(只需 `id` 和 `category`),`--all` 时会自动补全元数据。
