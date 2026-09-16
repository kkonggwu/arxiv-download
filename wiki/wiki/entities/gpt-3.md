---
type: entity
title: GPT-3
tags: [language-model, openai, autoregressive, few-shot-learning, in-context-learning]
related:
  - "[[openai]]"
  - "[[gpt-2]]"
  - "[[in-context-learning上下文学习]]"
  - "[[few-shot-learning]]"
  - "[[scaling-laws-for-neural-language-models神经语言模型缩放定律]]"
  - "[[common-crawl]]"
  - "[[webtext2]]"
  - "[[data-contamination]]"
  - "[[model-parallelism]]"
  - "[[byte-level-bpe]]"
  - "[[brown-2020-language-models-are-few-shot-learners]]"
created: 2026-09-16
updated: 2026-09-16
---

# GPT-3

GPT-3 是 OpenAI 于 2020 年发布的**自回归语言模型**，最大版本参数量 1750 亿（175 billion），比此前任何非稀疏（non-sparse）语言模型大 10 倍。论文《Language Models are Few-Shot Learners》以 GPT-3 为核心研究对象，主张扩大模型规模可显著提升任务无关的 few-shot 性能，且**所有任务均不做梯度更新或微调**。

## 模型系列（8 个规模）

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

架构约束：`dff = 4 * dmodel`；所有模型 `nctx = 2048` tokens；所有模型训练 300B tokens。

## 架构

GPT-3 使用与 [[gpt-2]] 相同的模型与架构，仅将注意力改为**交替的 dense 与 locally banded sparse attention**（参考 Sparse Transformer）。训练使用 [[model-parallelism]]（矩阵乘内并行 + 跨层并行），batch size 由 gradient noise scale 指导选择。

## 训练数据

| Dataset | Quantity (tokens) | Weight in training mix | Epochs elapsed when training for 300B tokens |
|---|---|---|---|
| Common Crawl (filtered) | 410 billion | 60% | 0.44 |
| WebText2 | 19 billion | 22% | 2.9 |
| Books1 | 12 billion | 8% | 1.9 |
| Books2 | 55 billion | 8% | 0.43 |
| Wikipedia | 3 billion | 3% | 3.4 |

按词数计 93% 为英文。采样权重不按数据集大小比例，高质量数据被有意过采样。

## 关键能力与结果

- **语言建模**：PTB zero-shot perplexity 20.50（以 15 点优势刷新 SOTA）；LAMBADA few-shot accuracy 86.4（比 SOTA 提升超 18%）。
- **闭卷问答**：TriviaQA few-shot 71.2%，在 closed-book 设定下相对微调模型为 SOTA；CoQA few-shot 85.0 F1。
- **翻译**：Fr→En few-shot 39.2 BLEU、De→En few-shot 40.6 BLEU；into-English 显著优于 from-English；En→Ro 异常低（21.0 BLEU），可能因复用 GPT-2 的英文 BPE tokenizer。
- **SuperGLUE**：few-shot 平均 71.8，超过微调 BERT-Large（69.0）；COPA 92.0、ReCoRD 90.2 接近 SOTA；WiC 仅 49.4（随机水平）。
- **算术**：2 位加法 few-shot 100%、2 位减法 98.9%、3 位加法 80.4%、3 位减法 94.2%；4–5 位运算 9–27%。
- **词解扰**：random insertion 66.9%、cycling letters 37.9%、较易 anagram 39.7%、较难 anagram 15.1%；reversed words 全部失败。
- **SAT Analogies**：few-shot 65.2%，高于大学申请者平均 57%。
- **新词使用**：给定虚构词定义后可生成正确或至少合理的用法（如为 "screeg" 生成屈折形式 "screeghed"）。
- **合成新闻**：人类辨识 GPT-3 175B 生成新闻的准确率仅约 52%（接近随机），control 模型为 86%–88%。

## 已知弱点

- 自然语言推理（[[anli]]、RTE）上 few-shot 仍挣扎；小于 GPT-3 的模型在 ANLI 上即使 few-shot 也几乎随机。
- 涉及比较两个句子/片段的任务（WiC、复述、蕴含）偏弱。
- 部分阅读理解任务（[[quac]]、[[race]]）表现弱。
- 文本合成仍会语义重复、长文失去连贯、自相矛盾、出现非逻辑句段。
- 在"常识物理"上表现差。
- 决策不可解释、校准差、继承数据偏见。

## 相关页面

[[openai]]、[[gpt-2]]、[[in-context-learning上下文学习]]、[[few-shot-learning]]、[[scaling-laws-for-neural-language-models神经语言模型缩放定律]]、[[data-contamination]]、[[model-parallelism]]、[[byte-level-bpe]]、[[brown-2020-language-models-are-few-shot-learners]]
