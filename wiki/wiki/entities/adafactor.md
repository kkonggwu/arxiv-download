---
type: entity
title: Adafactor
tags: [optimizer, training, memory-efficient]
related:
  - "[[adam]]"
  - "[[scaling-laws-for-neural-language-models神经语言模型缩放定律]]"
  - "[[kaplan-2020-scaling-laws-for-neural-language-models]]"
created: 2026-09-16
updated: 2026-09-16
---

# Adafactor

Adafactor 是本文在训练参数量超过 1B 的 Transformer 语言模型时使用的优化器（引用 [SS18]），用于替代 [[adam]] 以降低显存占用。

## 在本文中的使用

- 仅用于参数量 > 1B 的模型；较小模型使用 [[adam]]。
- 与 Adam 共享相同的训练配置：2.5×10^5 步、batch 512×1024、3000 步线性 warmup + cosine 衰减。
- 本文未报告 Adafactor 与 Adam 在缩放趋势上的系统性差异。

## 相关页面

- [[adam]] — 小模型使用的优化器
- [[scaling-laws-for-neural-language-models神经语言模型缩放定律]] — 本文核心概念