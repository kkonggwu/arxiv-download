---
type: entity
title: InstructGPT
tags: [model, openai, rlhf, instruction-following]
related:
  - "[[openai]]"
  - "[[gpt-3]]"
  - "[[rlhf基于人类反馈的强化学习]]"
  - "[[sft监督微调]]"
  - "[[reward-model奖励模型]]"
  - "[[ppo近端策略优化]]"
  - "[[ppo-ptx]]"
  - "[[alignment-tax对齐税]]"
  - "[[instruction-following指令遵循]]"
  - "[[6b-reward-model]]"
  - "[[ouyang-2022-instructgpt]]"
created: 2026-09-16
updated: 2026-09-16
---

# InstructGPT

InstructGPT 是 [[openai]] 在 Ouyang et al. 2022 中提出的模型系列，通过对 [[gpt-3]] 应用三阶段 [[rlhf基于人类反馈的强化学习]] 流程（[[sft监督微调]] → [[reward-model奖励模型]] → [[ppo近端策略优化]]）得到，目标是让模型行为更符合用户意图。

## 规模与变体

- 参数规模：1.3B、6B、175B。
- 训练变体：SFT、PPO（γ=0）、PPO-ptx（γ>0，混入预训练梯度）。
- 除非另有说明，论文中 "InstructGPT" 默认指 **PPO-ptx** 模型。

## 关键结果

- 1.3B InstructGPT 的输出在人类评估中优于 175B GPT-3（100x 参数差距）。
- 175B InstructGPT 相对 175B GPT-3 胜率 85±3%；相对 few-shot 175B GPT-3 胜率 71±4%。
- 相对 [[flan]] 胜率 78±4%，相对 [[t0]] 胜率 79±4%。
- [[truthfulqa]] 上真实性约提升一倍；闭域任务幻觉率从 41% 降至 21%。
- [[realtoxicityprompts]] 上毒性输出减少约 25%（在 "be respectful" 提示下）；去掉该指令后优势消失；显式要求有毒输出时反而比 GPT-3 更毒。
- [[winogender]]、[[crows-pairs]] 上偏见未显著改善。
- 对 RLHF 分布外的指令（非英语、代码）展现一定泛化能力，但常以英语输出。

## 局限

- 仍会犯简单错误：接受虚假前提、过度 hedge、多约束指令性能下降。
- 指令遵循改善不等于事实正确性提升（附录 F 中代码语义描述有误）。
- 最大局限：多数情况下遵循用户指令，即使可能导致现实世界危害。

## 相关页面

- [[gpt-3]]、[[openai]]、[[ppo-ptx]]、[[alignment-tax对齐税]]、[[instruction-following指令遵循]]