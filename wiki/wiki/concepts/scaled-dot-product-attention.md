---
type: concept
title: Scaled Dot-Product Attention
tags: [attention, transformer, mechanism, dot-product, architecture-component]
related:
  - "[[transformer]]"
  - "[[multi-head-attention]]"
  - "[[self-attention]]"
  - "[[vaswani-2017-attention-is-all-you-need]]"
created: 2026-09-16
updated: 2026-09-16
---

# Scaled Dot-Product Attention

Scaled Dot-Product Attention 是 [[transformer]] 中使用的注意力函数（现有版本表述）；新生成版本将其表述为 [[transformer]] 中注意力计算的「基本形式」。两种表述指向同一对象。

其输入为：

- 维度 `dk` 的查询（query，Q）与键（key，K）
- 维度 `dv` 的值（value，V）

## 公式

两个版本给出的公式一致：

```
Attention(Q, K, V ) = softmax(QK^T / √dk) V   (1)
```

## 缩放因子的理由

两版一致的核心论证：当 `dk` 较大时，点积幅值增大，将 softmax 推入梯度极小的区域；因此按 `1/√dk` 缩放（新生成版本的措辞为「按 1/√dk 缩放可抵消这一效应」）。

> [!note] 版本差异
> 「这是该机制区别于普通 dot-product attention 的关键设计」这一评价仅出现在新生成版本中；现有版本只陈述缩放的技术动机。

## 与 additive attention 的对比

论文对比了两种常用注意力函数。现有版本注明该对比位于论文的背景（background）部分——新生成版本亦注明此对比出自该文。

| 注意力函数 | 出处 | 特点 |
| --- | --- | --- |
| **Additive attention** | Bahdanau et al., 2014 | 使用带单隐层的前馈网络计算兼容性函数 |
| **Dot-product (multiplicative) attention** | Luong et al., 2015 | 即本文所用形式，但本文额外加入 `1/√dk` 缩放 |

两版一致给出的共同点与取舍：

- 二者理论复杂度相近。
- dot-product attention 在实践中更快、更省空间，因为它可用高度优化的矩阵乘法实现。

## 相关页面

- 来源（现有版本的 wikilink 形式）：[[vaswani-2017-attention-is-all-you-need]]
- 来源（新生成版本的 wikilink 形式）：[[vaswani-2017-attention-is-all-you-need]]
- 相关机制：[[multi-head-attention]]、[[self-attention]]
- 上层结构：[[transformer]]