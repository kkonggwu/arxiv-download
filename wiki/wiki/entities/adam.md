---
type: entity
title: Adam
tags: [optimizer, training, deep-learning]
related:
  - "[[adafactor]]"
  - "[[scaling-laws-for-neural-language-models神经语言模型缩放定律]]"
  - "[[kaplan-2020-scaling-laws-for-neural-language-models]]"
created: 2026-09-16
updated: 2026-09-16
---

# Adam

Adam 是本文训练 Transformer 语言模型时使用的主要优化器（引用 [KB14]）。

## 在本文中的使用

- 作为默认优化器用于全部模型训练。
- 当模型参数量超过 1B 时，改用 [[adafactor]] 以降低显存占用。
- 训练配置：2.5×10^5 步，batch 512×1024，3000 步线性 warmup + cosine 衰减。
- 本文发现学习率调度选择基本无关，只要总学习率足够大且包含 warmup 与最终衰减；run-to-run 波动约 0.05。
- 学习率经验公式 LR(N) ≈ 0.003239 − 0.0001395 log(N)（式 D.1），在 N > 10^10 时失效。

## 相关页面

- [[adafactor]] — 大模型训练时替代 Adam 的优化器
- [[scaling-laws-for-neural-language-models神经语言模型缩放定律]] — 本文核心概念