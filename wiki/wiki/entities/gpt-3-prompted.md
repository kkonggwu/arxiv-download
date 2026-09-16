---
type: entity
title: GPT-3-prompted
tags: [model, baseline, language-model, few-shot]
related:
  - "[[gpt-3]]"
  - "[[instructgpt]]"
  - "[[openai]]"
  - "[[in-context-learning上下文学习]]"
  - "[[ouyang-2022-instructgpt]]"
created: 2026-09-16
updated: 2026-09-16
---

# GPT-3-prompted

## 概述

**GPT-3-prompted** 是 Ouyang et al. (2022) 在 InstructGPT 论文中使用的基线模型之一，指通过 few-shot 前缀提示（few-shot prompting）方式使用的 GPT-3 175B。它并非一个独立训练的模型，而是对原始 [[gpt-3]] 施加精心设计的 few-shot 提示后得到的推理配置，用于与经过人类反馈微调的 [[instructgpt]] 进行对比。

## 在论文中的角色

在 InstructGPT 的人类评估实验中，GPT-3-prompted 作为强基线出现：

- **175B InstructGPT vs. GPT-3-prompted（175B）**：胜率为 **71±4%**。这一对比说明，即使给 GPT-3 提供 few-shot 示例，InstructGPT 仍显著更受标注员偏好。
- 与之对照，175B InstructGPT 相对**零样本** 175B GPT-3 的胜率为 **85±3%**，说明 few-shot 提示确实能缩小一部分差距，但无法弥合。

## 与相关基线的区别

| 基线 | 说明 |
|------|------|
| GPT-3（175B） | 零样本直接推理的原始模型 |
| **GPT-3-prompted** | 施加 few-shot 前缀提示的 GPT-3 175B |
| FLAN 微调 | 在约 100 万样本上做指令微调的基线 |
| T0 / T0++ 微调 | 多任务指令微调基线 |

论文指出，公开 NLP 数据集上的指令微调基线（FLAN、T0/T0++）在 OpenAI API 的真实使用分布上表现不佳：InstructGPT 相对这些基线胜率 73.4±2%，而 T0 与 FLAN 版本分别仅 26.8±2%、29.8±2%。GPT-3-prompted 则代表了"不微调、仅靠提示"这一路线的上限参照。

## 意义

GPT-3-prompted 的存在凸显了论文的核心论点之一：**仅靠提示工程（prompting）不足以让大模型可靠地遵循用户意图**，而基于人类反馈的微调（[[rlhf]]）能带来实质性的对齐改进。这也与 [[in-context-learning上下文学习]] 的能力边界相关——few-shot 提示能激活部分能力，但无法替代针对指令遵循目标的专门训练。

## 相关页面

- [[gpt-3]] — 基础模型
- [[instructgpt]] — 经 RLHF 微调的对应模型
- [[openai]] — 开发机构
- [[ouyang-2022-instructgpt]] — 来源论文
- [[in-context-learning上下文学习]] — few-shot 提示所依赖的机制