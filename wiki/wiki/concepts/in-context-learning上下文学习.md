---
type: concept
title: In-Context Learning（上下文学习）
tags: [few-shot-learning, meta-learning, language-modeling, gpt-3]
related:
  - "[[gpt-3]]"
  - "[[openai]]"
  - "[[brown-2020-language-models-are-few-shot-learners]]"
  - "[[zero-shot-learning]]"
  - "[[one-shot-learning]]"
  - "[[few-shot-learning]]"
  - "[[meta-learning]]"
  - "[[scaling-laws-for-neural-language-models神经语言模型缩放定律]]"
  - "[[data-contamination]]"
created: 2026-09-16
updated: 2026-09-16
---

# In-Context Learning（上下文学习）

## 定义

In-context learning（上下文学习）指语言模型在不进行任何梯度更新或参数微调的前提下，仅凭推理时输入提示（prompt）中给出的任务描述与少量示例，就能完成该任务的现象。任务与示例完全以自然语言文本的形式在上下文中指定，模型通过一次前向传播直接产生答案。

这一术语由 Brown 等人在《Language Models are Few-Shot Learners》（2020, arXiv:2005.14165）中提出并系统化，作为 GPT-3 的核心能力主张。

## 与元学习框架的关系

论文将 in-context learning 置于 meta-learning（元学习）框架下理解：

- **外循环（outer loop）**：预训练阶段。模型在大规模语料上习得广泛的技能与模式识别能力，相当于元学习中的"学习如何学习"。
- **内循环（inner loop）**：推理阶段。模型在单次前向传播内，根据上下文中的示例快速适配到具体任务，不发生权重更新。

因此，上下文学习可视为一种"前向传播内的快速适配"，而非传统意义上的参数优化。

## 按示例数量的细分设定

论文按推理时提供的示例数量，将评估划分为三种条件：

| 设定 | 示例数量 | 说明 |
|------|----------|------|
| zero-shot | 0 | 仅给出自然语言任务指令 |
| one-shot | 1 | 给出一个示例 |
| few-shot | 通常 10–100 | 在上下文窗口（nctx = 2048）内尽可能多地给出示例 |

所有设定均**不做梯度更新或微调**，与传统的 Fine-Tuning (FT) 设定形成对照。

## 关键证据

论文在超过两打（over two dozen）NLP 数据集上评估 GPT-3，代表性结果包括：

- **CoQA**：zero-shot 81.5 F1、one-shot 84.0 F1、few-shot 85.0 F1。
- **TriviaQA**：zero-shot 64.3%、one-shot 68.0%、few-shot 71.2%；few-shot 结果在 closed-book 设定下相对微调模型达到 SOTA。

展示出的能力涵盖翻译、问答、cloze、词序还原（unscrambling words）、3 位数算术，以及在句中首次定义后使用新词（novel word usage）。在 few-shot 条件下，模型还能生成人类评估者难以区分真伪的合成新闻文章。

## In-Context Learning Curves

论文观察到，随着模型规模增大，few-shot 性能的提升幅度通常大于 zero-shot，即上下文学习的能力随规模增长而增强。这一现象被称为 in-context learning curves，是"规模扩大提升任务无关 few-shot 性能"这一核心主张的直接证据。

## 局限与失败案例

- 在自然语言推理任务（如 ANLI）上，few-shot 表现仍然挣扎。
- 在部分阅读理解数据集（如 RACE、QuAC）上表现不佳。
- 部分数据集存在与大规模网络语料训练相关的方法论问题，即训练集污染（data contamination），论文用星号标记受影响的结果。

## 相关页面

- [[gpt-3]] — 承载该能力的 175B 参数模型
- [[brown-2020-language-models-are-few-shot-learners]] — 提出该术语的原始论文
- [[meta-learning]] — 内循环/外循环框架
- [[zero-shot-learning]]、[[one-shot-learning]]、[[few-shot-learning]] — 按示例数量划分的设定
- [[scaling-laws-for-neural-language-models神经语言模型缩放定律]] — 规模与上下文学习能力的关系
- [[data-contamination]] — 评估中的方法论风险