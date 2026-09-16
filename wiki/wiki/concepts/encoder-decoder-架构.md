---
type: concept
title: Encoder-Decoder 架构
tags: [architecture, transformer, sequence-transduction]
related:
  - "[[transformer]]"
  - "[[self-attention]]"
  - "[[multi-head-attention]]"
  - "[[position-wise-feed-forward-networks逐位置前馈网络]]"
  - "[[positional-encoding]]"
  - "[[vaswani-2017-attention-is-all-you-need]]"
created: 2026-09-16
updated: 2026-09-16
---

# Encoder-Decoder 架构

在 [[transformer]] 语境下，编码器与解码器各由 N = 6 层相同结构堆叠构成。

## 通用子层结构

编码器与解码器中，每个子层都采用残差连接与层归一化，形式为：

```
LayerNorm(x + Sublayer(x))
```

该形式同时适用于编码器各子层与解码器各子层。

## 编码器

每层包含两个子层：

1. [[multi-head-attention]]（multi-head self-attention）。
2. [[position-wise-feed-forward-networks逐位置前馈网络]]（position-wise feed-forward network）。

## 解码器

每层包含三个子层：

1. Masked [[multi-head-attention]]（masked multi-head self-attention）——防止位置关注后续位置，保持 auto-regressive 解码性质。
2. Encoder-decoder attention——查询来自解码器，键与值来自编码器输出。
3. [[position-wise-feed-forward-networks逐位置前馈网络]]（position-wise feed-forward network）。

## 注意力的三种应用

1. Encoder-decoder attention。
2. Encoder self-attention。
3. Masked self-attention。

## 相关组件

- [[self-attention]]
- [[multi-head-attention]]
- [[position-wise-feed-forward-networks逐位置前馈网络]]
- [[positional-encoding]]

## 相关页面

- 来源：[[vaswani-2017-attention-is-all-you-need]]