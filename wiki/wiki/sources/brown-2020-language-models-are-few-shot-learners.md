---
type: source
title: Language Models are Few-Shot Learners (GPT-3)
tags: [gpt-3, few-shot-learning, in-context-learning, scaling-laws, language-model, openai, benchmark-contamination, bias]
related:
  - "[[gpt-3]]"
  - "[[openai]]"
  - "[[in-context-learning上下文学习]]"
  - "[[few-shot-learning]]"
  - "[[zero-shot-learning]]"
  - "[[one-shot-learning]]"
  - "[[meta-learning]]"
  - "[[scaling-laws-for-neural-language-models神经语言模型缩放定律]]"
  - "[[data-contamination]]"
  - "[[common-crawl]]"
  - "[[webtext2]]"
  - "[[lambada]]"
  - "[[triviaqa]]"
  - "[[superglue]]"
  - "[[anli]]"
  - "[[hellaswag]]"
  - "[[arc]]"
  - "[[openbookqa]]"
  - "[[piqa]]"
  - "[[winograd]]"
  - "[[winogrande]]"
  - "[[race]]"
  - "[[quac]]"
  - "[[drop]]"
  - "[[squad-2-0]]"
  - "[[coqa]]"
  - "[[natural-questions]]"
  - "[[webquestions]]"
  - "[[wmt-2014-fr-en]]"
  - "[[wmt-2016-de-en]]"
  - "[[wmt-2016-ro-en]]"
  - "[[sat-analogies]]"
  - "[[winogender]]"
  - "[[senti-wordnet]]"
  - "[[bert]]"
  - "[[roberta]]"
  - "[[t5]]"
  - "[[gpt-2]]"
  - "[[xlm]]"
  - "[[mass]]"
  - "[[mbart]]"
  - "[[rag]]"
  - "[[unifiedqa]]"
  - "[[albert]]"
  - "[[mixture-of-experts]]"
  - "[[model-parallelism]]"
  - "[[fuzzy-deduplication]]"
  - "[[byte-level-bpe]]"
  - "[[human-detection-of-model-generated-text]]"
  - "[[benchmark-memorization]]"
  - "[[broader-impacts-of-language-models]]"
  - "[[energy-usage-of-language-models]]"
  - "[[hu-2021-lora]]"
  - "[[vaswani-2017-attention-is-all-you-need]]"
authors: [Tom B. Brown, Benjamin Mann, Nick Ryder, Melanie Subbiah, Jared Kaplan, Prafulla Dhariwal, Arvind Neelakantan, Pranav Shyam, Girish Sastry, Amanda Askell, Sandhini Agarwal, Ariel Herbert-Voss, Gretchen Krueger, Tom Henighan, Rewon Child, Aditya Ramesh, Daniel M. Ziegler, Jeffrey Wu, Clemens Winter, Christopher Hesse, Mark Chen, Eric Sigler, Mateusz Litwin, Scott Gray, Benjamin Chess, Jack Clark, Christopher Berner, Sam McCandlish, Alec Radford, Ilya Sutskever, Dario Amodei]
year: 2020
url: "https://arxiv.org/abs/2005.14165"
venue: "NeurIPS 2020"
created: 2026-09-16
updated: 2026-09-16
---

# Language Models are Few-Shot Learners（GPT-3）

## 一句话总结

OpenAI 训练了 1750 亿参数的自回归语言模型 GPT-3，并证明：**仅靠扩大模型规模，就能显著提升任务无关的 few-shot 性能**——所有任务都不做梯度更新或微调，任务与示例完全通过文本上下文指定，部分任务上 few-shot 结果接近甚至超过此前需要微调的 SOTA 系统。

## 核心贡献

1. **GPT-3 模型本身**：175B 参数自回归语言模型，比此前任何非稀疏（non-sparse）语言模型大 10 倍；架构与 GPT-2 相同，仅将注意力改为交替的 dense 与 locally banded sparse attention。
2. **in-context learning 框架**：提出并系统化 [[in-context-learning上下文学习]] 与 [[meta-learning]] 术语——预训练阶段习得广泛技能与模式识别能力，推理时通过前向传播内的"内循环"快速适配任务，无需参数更新。
3. **四种评估设定谱系**：Fine-Tuning (FT)、Few-Shot (FS)、One-Shot (1S)、Zero-Shot (0S)，在超过两打 NLP 数据集上系统对比。
4. **规模与 few-shot 性能的关系**：zero/one/few-shot 性能随模型容量平滑 scaling，且 zero/one/few-shot 之间的差距常随容量增大而扩大（暗示大模型是更强的 meta-learner）。
5. **数据污染的系统性研究**：为每个基准构造 clean subset（13-gram 重叠判据），量化残留污染对性能的影响，并对可疑数据集加星号标记。
6. **偏见与公平性分析**：性别、种族、宗教三个维度的初步量化分析。
7. **人类辨识实验**：证明人类区分 GPT-3 生成新闻与人类写作的能力随模型规模增大而下降至接近随机水平。

## 模型规模与架构（Table 2.1）

所有模型训练 300B tokens；架构约束 `dff = 4 * dmodel`，所有模型 `nctx = 2048` tokens。

| Model Name | nparams | nlayers | dmodel | nheads | dhead | Batch Size | Learning Rate |
|---|---|---|---|---|---|---|---|
| GPT-3 Small | 125M | 12 | 768 | 12 | 64 | 0.5M | 6.0 × 10⁻⁴ |
| GPT-3 Medium | 350M | 24 | 1024 | 16 | 64 | 0.5M | 3.0 × 10⁻⁴ |
| GPT-3 Large | 760M | 24 | 1536 | 16 | 96 | 0.5M | 2.5 × 10⁻⁴ |
| GPT-3 XL | 1.3B | 24 | 2048 | 24 | 128 | 1M | 2.0 × 10⁻⁴ |
| GPT-3 2.7B | 2.7B | 32 | 2560 | 32 | 80 | 1M | 1.6 × 10⁻⁴ |
| GPT-3 6.7B | 6.7B | 32 | 4096 | 32 | 128 | 2M | 1.2 × 10⁻⁴ |
| GPT-3 13B | 13.0B | 40 | 5140 | 40 | 128 | 2M | 1.0 × 10⁻⁴ |
| GPT-3 175B or "GPT-3" | 175.0B | 96 | 12288 | 96 | 128 | 3.2M | 0.6 × 10⁻⁴ |

## 训练数据混合（Table 2.2）

| Dataset | Quantity (tokens) | Weight in training mix | Epochs elapsed when training for 300B tokens |
|---|---|---|---|
| Common Crawl (filtered) | 410 billion | 60% | 0.44 |
| WebText2 | 19 billion | 22% | 2.9 |
| Books1 | 12 billion | 8% | 1.9 |
| Books2 | 55 billion | 8% | 0.43 |
| Wikipedia | 3 billion | 3% | 3.4 |

训练数据按词数计 93% 为英文。Common Crawl 原始为 41 个 shard（2016–2019，45TB 压缩纯文本），经自动过滤后为 570GB。采样权重不按数据集大小比例，高质量数据被有意过采样。

## 主要结果

### 语言建模 / Cloze / 补全（Table 3.2）

| Setting | LAMBADA (acc) | LAMBADA (ppl) | StoryCloze (acc) | HellaSwag (acc) |
|---|---|---|---|---|
| SOTA | 68.0a | 8.63b | 91.8c | 85.6d |
| GPT-3 Zero-Shot | 76.2 | 3.00 | 83.2 | 78.9 |
| GPT-3 One-Shot | 72.5 | 3.35 | 84.7 | 78.1 |
| GPT-3 Few-Shot | 86.4 | 1.92 | 87.7 | 79.3 |

（a[Tur20] b[RWC+19] c[LDL19] d[LCH+20]）PTB 上 GPT-3 zero-shot perplexity 20.50，以 15 点优势刷新 SOTA。

### 闭卷开放域问答（Table 3.3）

| Setting | NaturalQS | WebQS | TriviaQA |
|---|---|---|---|
| RAG (Fine-tuned, Open-Domain) [LPP+20] | 44.5 | 45.5 | 68.0 |
| T5-11B+SSM (Fine-tuned, Closed-Book) [RRS20] | 36.6 | 44.7 | 60.5 |
| T5-11B (Fine-tuned, Closed-Book) | 34.5 | 37.4 | 50.1 |
| GPT-3 Zero-Shot | 14.6 | 14.4 | 64.3 |
| GPT-3 One-Shot | 23.0 | 25.3 | 68.0 |
| GPT-3 Few-Shot | 29.9 | 41.5 | 71.2 |

### 翻译 BLEU（Table 3.4）

| Setting | En→Fr | Fr→En | En→De | De→En | En→Ro | Ro→En |
|---|---|---|---|---|---|---|
| SOTA (Supervised) | 45.6a | 35.0b | 41.2c | 40.2d | 38.5e | 39.9e |
| XLM [LC19] | 33.4 | 33.3 | 26.4 | 34.3 | 33.3 | 31.8 |
| MASS [STQ+19] | 37.5 | 34.9 | 28.3 | 35.2 | 35.2 | 33.1 |
| mBART [LGG+20] | - | - | 29.8 | 34.0 | 35.0 | 30.5 |
| GPT-3 Zero-Shot | 25.2 | 21.2 | 24.6 | 27.2 | 14.1 | 19.9 |
| GPT-3 One-Shot | 28.3 | 33.7 | 26.2 | 30.4 | 20.6 | 38.6 |
| GPT-3 Few-Shot | 32.6 | 39.2 | 29.7 | 40.6 | 21.0 | 39.5 |

SacreBLEU signature: `BLEU+case.mixed+numrefs.1+smooth.exp+tok.intl+version.1.2.20`

### Winograd / Winogrande（Table 3.5）

| Setting | Winograd | Winogrande (XL) |
|---|---|---|
| Fine-tuned SOTA | 90.1a | 84.6b |
| GPT-3 Zero-Shot | 88.3* | 70.2 |
| GPT-3 One-Shot | 89.7* | 73.2 |
| GPT-3 Few-Shot | 88.6* | 77.7 |

### 常识推理（Table 3.6）

| Setting | PIQA | ARC (Easy) | ARC (Challenge) | OpenBookQA |
|---|---|---|---|---|
| Fine-tuned SOTA | 79.4 | 92.0 | 78.5 | 87.2 |
| GPT-3 Zero-Shot | 80.5* | 68.8 | 51.4 | 57.6 |
| GPT-3 One-Shot | 80.5* | 71.2 | 53.2 | 58.8 |
| GPT-3 Few-Shot | 82.8* | 70.1 | 51.5 | 65.4 |

### 阅读理解（Table 3.7，除 RACE 为 accuracy 外均为 F1）

| Setting | CoQA | DROP | QuAC | SQuADv2 | RACE-h | RACE-m |
|---|---|---|---|---|---|---|
| Fine-tuned SOTA | 90.7a | 89.1b | 74.4c | 93.0d | 90.0e | 93.1e |
| GPT-3 Zero-Shot | 81.5 | 23.6 | 41.5 | 59.5 | 45.5 | 58.4 |
| GPT-3 One-Shot | 84.0 | 34.3 | 43.3 | 65.4 | 45.9 | 57.4 |
| GPT-3 Few-Shot | 85.0 | 36.5 | 44.3 | 69.8 | 46.8 | 58.1 |

### SuperGLUE（Table 3.8，test set）

| Setting | Average | BoolQ Acc | CB Acc | CB F1 | COPA Acc | RTE Acc |
|---|---|---|---|---|---|---|
| Fine-tuned SOTA | 89.0 | 91.0 | 96.9 | 93.9 | 94.8 | 92.5 |
| Fine-tuned BERT-Large | 69.0 | 77.4 | 83.6 | 75.7 | 70.6 | 71.7 |
| GPT-3 Few-Shot | 71.8 | 76.4 | 75.6 | 52.0 | 92.0 | 69.0 |

| Setting | WiC Acc | WSC Acc | MultiRC Acc | MultiRC F1a | ReCoRD Acc | ReCoRD F1 |
|---|---|---|---|---|---|---|
| Fine-tuned SOTA | 76.1 | 93.8 | 62.3 | 88.2 | 92.5 | 93.3 |
| Fine-tuned BERT-Large | 69.6 | 64.6 | 24.1 | 70.0 | 71.3 | 72.0 |
| GPT-3 Few-Shot | 49.4 | 80.1 | 30.5 | 75.4 | 90.2 | 91.1 |

### 算术（Table 3.9，GPT-3 175B）

| Setting | 2D+ | 2D- | 3D+ | 3D- | 4D+ | 4D- | 5D+ | 5D- | 2Dx | 1DC |
|---|---|---|---|---|---|---|---|---|---|---|
| GPT-3 Zero-shot | 76.9 | 58.0 | 34.2 | 48.3 | 4.0 | 7.5 | 0.7 | 0.8 | 19.8 | 9.8 |
| GPT-3 One-shot | 99.6 | 86.4 | 65.5 | 78.7 | 14.0 | 14.0 | 3.5 | 3.8 | 27.4 | 14.3 |
| GPT-3 Few-shot | 100.0 | 98.9 | 80.4 | 94.2 | 25.5 | 26.8 | 9.3 | 9.9 | 29.2 | 21.3 |

### 词解扰 / 字符操作（Table 3.10，GPT-3 175B）

| Setting | CL | A1 | A2 | RI | RW |
|---|---|---|---|---|---|
| GPT-3 Zero-shot | 3.66 | 2.28 | 8.91 | 8.26 | 0.09 |
| GPT-3 One-shot | 21.7 | 8.62 | 25.9 | 45.4 | 0.48 |
| GPT-3 Few-shot | 37.9 | 15.1 | 39.7 | 67.2 | 0.44 |

### 人类辨识合成新闻（Table 3.11，约 200 词）

| 模型 | Mean accuracy | 95% CI (low, hi) | t vs control (p-value) | "I don't know" |
|------|--------------|------------------|------------------------|----------------|
| Control (deliberately bad model) | 86% | 83%–90% | - | 3.6% |
| GPT-3 Small | 76% | 72%–80% | 3.9 (2e-4) | 4.9% |
| GPT-3 Medium | 61% | 58%–65% | 10.3 (7e-21) | 6.0% |
| GPT-3 Large | 68% | 64%–72% | 7.3 (3e-11) | 8.7% |
| GPT-3 XL | 62% | 59%–65% | 10.7 (1e-19) | 7.5% |
| GPT-3 2.7B | 62% | 58%–65% | 10.4 (5e-19) | 7.1% |
| GPT-3 6.7B | 60% | 56%–63% | 11.2 (3e-21) | 6.2% |
| GPT-3 13B | 55% | 52%–58% | 15.3 (1e-32) | 7.1% |
| GPT-3 175B | 52% | 49%–54% | 16.9 (1e-34) | 7.8% |

### 人类辨识合成新闻（Table 3.12，约 500 词）

| 模型 | Mean accuracy | 95% CI (low, hi) | t vs control (p-value) | "I don't know" |
|------|--------------|------------------|------------------------|----------------|
| Control | 88% | 84%–91% | - | 2.7% |
| GPT-3 175B | 52% | 48%–57% | 12.7 (3.2e-23) | 10.6% |

## 数据污染分析（第 4 节）

方法：为每个基准构造 clean subset，移除所有与预训练集存在 13-gram 重叠的样本（样本短于 13-gram 时整体重叠者移除），保守标记任何潜在污染。N 取各数据集第 5 百分位示例长度（词数），非合成任务最小 N=8、最大 N=13；用 Apache Spark 计算精确碰撞。

关键结论：
- 潜在污染常很高（约四分之一基准超过 50%），但多数情况下性能变化可忽略，且污染水平与性能差异无相关性。
- 阅读理解三数据集（QuAC、SQuAD2、DROP）>90% 被标记，但人工检查发现源文本在训练集中而问答对不在，模型仅获得背景信息。
- WMT16 De-En 25% 被标记，总效应 1–2 BLEU，无成对 NMT 训练数据式匹配。
- PIQA 29% 被标记、干净子集性能绝对下降 3 个百分点（相对 4%），但 25 倍小模型也出现类似下降，疑为统计偏差，故加星号。
- Winograd 45% 被标记、干净子集下降 2.6%，132 个 Winograd schema 确实存在于训练集但格式不同，故加星号。
- 4 个 Wikipedia 语言建模基准 + Children's Book Test 几乎完全包含在训练数据中，无法可靠抽取 clean subset，故不报告结果；PTB 因年代久远未受影响，成为主要语言建模基准。
- 因过滤 bug 只完成了部分重叠移除，且因训练成本无法重训。

## 局限（第 5 节）

- 文本合成仍会语义重复、长文失去连贯、自相矛盾、出现非逻辑句段。
- 在"常识物理"上表现差（如"把奶酪放进冰箱会融化吗"）。
- 在 comparison 类任务（WiC、ANLI）及部分阅读理解任务（QuAC、RACE）上 one/few-shot 接近随机。
- 结构性局限：仅用自回归模型，未含双向架构或去噪目标，可能在 fill-in-the-blank、回看比较、长文重读后短答等任务上吃亏。
- 预训练目标本身可能触及上限（每 token 等权、缺乏重要性概念、任务需强行转为预测问题、缺乏多模态 grounding）。
- 预训练样本效率差（远超人类一生阅读量）。
- few-shot 是否真正"从零学习"存在不确定性。
- 推理昂贵不便，蒸馏是潜在方向；决策不可解释、校准差、继承数据偏见。

## 更广泛影响（第 6 节）

- **滥用（6.1）**：misinformation、spam、phishing、滥用法律与政府流程、学术论文代写欺诈、社会工程 pretexting。威胁行为者从低/中技能到 APT；GPT-2 发布后 APT 操作无可辨差异。语言模型输出随机性限制滥用操作的可扩展性。
- **偏见与公平性（6.2）**：388 个职业中 83% 更可能接男性标识词；平均职业偏见指标 Neutral −1.11、Competent −2.14、Incompetent −1.15。GPT-3 175B 在 Winogender 上准确率最高（64.17%）。'Asian' 情感持续偏高、'Black' 持续偏低。Islam 与 violent、terrorism、terrorist 共现率更高。
- **能耗（6.3）**：训练 GPT-3 175B 消耗数千 petaflop/s-days；生成 100 页内容约耗 0.4 kW-hr。

### Table 6.1: Most Biased Descriptive Words in 175B Model

| Top 10 Most Biased Male Descriptive Words (Raw Co-Occurrence Counts) | Top 10 Most Biased Female Descriptive Words (Raw Co-Occurrence Counts) |
|---|---|
| Large (16) | Optimistic (12) |
| Mostly (15) | Bubbly (12) |
| Lazy (14) | Naughty (12) |
| Fantastic (13) | Easy-going (12) |
| Eccentric (13) | Petite (10) |
| Protect (10) | Tight (10) |
| Jolly (10) | Pregnant (10) |
| Stable (9) | Gorgeous (28) |
| Personable (22) | Sucked (8) |
| Survive (7) | Beautiful (158) |

Average Number of Co-Occurrences Across All Words: Male 17.5；Female 23.9

### Table 6.2: Ten most favored words about each religion in the GPT-3 175B model

| Religion | Most Favored Descriptive Words |
|---|---|
| Atheism | 'Theists', 'Cool', 'Agnostics', 'Mad', 'Theism', 'Defensive', 'Complaining', 'Correct', 'Arrogant', 'Characterized' |
| Buddhism | 'Myanmar', 'Vegetarians', 'Burma', 'Fellowship', 'Monk', 'Japanese', 'Reluctant', 'Wisdom', 'Enlightenment', 'Non-Violent' |
| Christianity | 'Attend', 'Ignorant', 'Response', 'Judgmental', 'Grace', 'Execution', 'Egypt', 'Continue', 'Comments', 'Officially' |
| Hinduism | 'Caste', 'Cows', 'BJP', 'Kashmir', 'Modi', 'Celebrated', 'Dharma', 'Pakistani', 'Originated', 'Africa' |
| Islam | 'Pillars', 'Terrorism', 'Fasting', 'Sheikh', 'Non-Muslim', 'Source', 'Charities', 'Levant', 'Allah', 'Prophet' |
| Judaism | 'Gentiles', 'Race', 'Semites', 'Whites', 'Blacks', 'Smartest', 'Racists', 'Arabs', 'Game', 'Russian' |

## 附录要点

- **附录 A**：Common Crawl 自动过滤（以 WebText 为高质量代理训练 logistic regression 分类器，特征来自 Spark 标准 tokenizer 与 HashingTF；Pareto 重采样规则 `np.random.pareto(α) > 1 − document_score`，α = 9）；fuzzy deduplication 使用 Spark MinHashLSH（10 hashes），平均减少数据集约 10%。
- **附录 B**：训练超参数——Adam（β1=0.9, β2=0.95, ε=10⁻⁸）、梯度全局范数裁剪 1.0、cosine decay 至原值 10%、前 375M tokens 线性 LR warmup、batch size 从 32k tokens 线性增至满值、weight decay 0.1；始终训练完整 nctx=2048 上下文窗口，短文档打包。
- **附录 C**：污染研究细节与 Table C.1（各数据集重叠统计）。
- **附录 D**：训练算力计算（Table D.1），忽略 attention（<10% 总算力），每 token 每活跃参数前向 1 次加法 + 1 次乘法，反向乘 3x。
- **附录 E**：合成新闻人类评估细节（Table E.1/E.2），718 名参与者、6 个实验、621 人有效。
- **附录 F**：GPT-3 以 Wallace Stevens 风格生成诗歌样本（temperature 1、nucleus sampling P=0.9）。
- **附录 G**：Figure G.1–G.51，全部任务的格式化示例（Context → Correct/Incorrect Answer 或 Target Completion）。
- **附录 H**：Table H.1 全任务全设定全模型分数表，以及 Figure H.1–H.11 按任务族汇总的结果图。

## 相关页面

- 模型与机构：[[gpt-3]]、[[openai]]、[[gpt-2]]、[[bert]]、[[roberta]]、[[t5]]、[[xlm]]、[[mass]]、[[mbart]]、[[rag]]、[[unifiedqa]]、[[albert]]、[[mixture-of-experts]]
- 核心概念：[[in-context-learning上下文学习]]、[[few-shot-learning]]、[[zero-shot-learning]]、[[one-shot-learning]]、[[meta-learning]]、[[scaling-laws-for-neural-language-models神经语言模型缩放定律]]、[[data-contamination]]、[[benchmark-memorization]]、[[model-parallelism]]、[[fuzzy-deduplication]]、[[byte-level-bpe]]、[[human-detection-of-model-generated-text]]、[[broader-impacts-of-language-models]]、[[energy-usage-of-language-models]]
- 数据集：[[common-crawl]]、[[webtext2]]、[[lambada]]、[[triviaqa]]、[[superglue]]、[[anli]]、[[hellaswag]]、[[arc]]、[[openbookqa]]、[[piqa]]、[[winograd]]、[[winogrande]]、[[race]]、[[quac]]、[[drop]]、[[squad-2-0]]、[[coqa]]、[[natural-questions]]、[[webquestions]]、[[wmt-2014-fr-en]]、[[wmt-2016-de-en]]、[[wmt-2016-ro-en]]、[[sat-analogies]]、[[winogender]]、[[senti-wordnet]]
- 相关来源：[[vaswani-2017-attention-is-all-you-need]]、[[hu-2021-lora]]
