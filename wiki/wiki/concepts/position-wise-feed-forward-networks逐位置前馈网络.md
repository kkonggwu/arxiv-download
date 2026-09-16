---
type: concept
title: Position-wise Feed-Forward Networks（逐位置前馈网络）
tags: [transformer, neural-network-architecture, feed-forward-network, attention]
related:
  - "[[transformer]]"
  - "[[multi-head-attention]]"
  - "[[scaled-dot-product-attention]]"
  - "[[self-attention]]"
  - "[[residual-connection]]"
  - "[[layer-normalization]]"
  - "[[positional-encoding]]"
  - "[[vaswani-2017-attention-is-all-you-need]]"
created: 2026-09-16
updated: 2026-09-16
---

# Position-wise Feed-Forward Networks（逐位置前馈网络）

## 定义

Position-wise Feed-Forward Networks（逐位置前馈网络，简称 FFN）是 Transformer 编码器与解码器中每个子层（sub-layer）的第二个组成部分，紧随 [[multi-head-attention]] 之后。它由两个线性变换（linear transformation）与中间的一个 ReLU 激活函数构成，对序列中的**每一个位置独立且相同地**施加：

```
FFN(x) = max(0, xW1 + b1)W2 + b2   (2)
```

其中 `W1`、`W2`、`b1`、`b2` 为可学习参数。虽然该变换在不同位置之间共享同一组参数，但层与层之间使用不同的参数（即第 i 层与第 j 层的 FFN 参数不同）。

## 关键性质

- **逐位置（position-wise）**：同一 FFN 独立作用于序列的每个位置，位置之间无信息交互；跨位置的信息交换完全由注意力子层承担。
- **逐层不同**：论文原文指出，这可以等价地描述为两个 kernel size 为 1 的卷积（kernel size 1 convolutions），但层与层之间参数不共享。
- **维度变换**：输入与输出维度均为 `dmodel = 512`，内层维度 `dff = 2048`。即先由 `512 → 2048` 升维，经 ReLU 后再由 `2048 → 512` 降维。
- **参数共享范围**：同一层内所有位置共享参数，不同层之间不共享。

## 在 Transformer 中的位置

每个编码器层（encoder layer）包含两个子层：

1. Multi-Head Self-Attention
2. Position-wise Feed-Forward Network

每个解码器层（decoder layer）包含三个子层：

1. Masked Multi-Head Self-Attention
2. Encoder-Decoder Attention
3. Position-wise Feed-Forward Network

每个子层都包裹在残差连接（residual connection）与层归一化（layer normalization）之中，即输出为：

```
LayerNorm(x + Sublayer(x))
```

## 超参数

| 参数 | 值 |
|------|-----|
| N（编码器/解码器层数） | 6 |
| dmodel | 512 |
| dff（FFN 内层维度） | 2048 |
| h（注意力头数） | 8 |
| dk = dv | dmodel/h = 64 |

## base 与 big 配置

- base：`dmodel = 512`、`dff = 2048`
- big：`dmodel = 1024`、`dff = 4096`

（原文第 3.3 节："the dimensionality of input and output is dmodel = 512, and the inner-layer has dimensionality dff = 2048"；big 模型为 dmodel = 1024、dff = 4096。）

## 与注意力子层的分工

在 Transformer 的设计中，注意力子层负责在位置之间聚合信息，而 FFN 子层则对每个位置独立地进行非线性特征变换。二者交替堆叠，使模型既能建模全局依赖，又能对每个位置的表征做逐点的非线性加工。论文的注意力可视化（Figure 3–5）主要针对注意力子层，未对 FFN 的功能分化做可视化分析。

## 相关概念

- [[multi-head-attention]] — FFN 之前的子层，负责跨位置信息聚合
- [[scaled-dot-product-attention]] — 注意力计算的核心形式
- [[self-attention]] — 编码器/解码器自注意力
- [[residual-connection]] — 每个子层的外层包裹结构
- [[layer-normalization]] — 每个子层的外层归一化
- [[positional-encoding]] — 为无循环结构注入位置信息
- [[transformer]] — 该组件的宿主架构

## 来源

- Vaswani et al., 2017, *Attention Is All You Need*, NIPS 2017, arXiv:1706.03762v7，第 3.3 节（Position-wise Feed-Forward Networks）与第 3.1 节（Encoder and Decoder Stacks）。