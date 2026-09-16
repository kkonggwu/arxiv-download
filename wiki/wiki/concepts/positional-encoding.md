---
type: concept
title: Positional Encoding
tags: [transformer, positional-encoding, architecture, position-representation, sequence-modeling, architecture-component]
related:
  - "[[transformer]]"
  - "[[self-attention]]"
  - "[[why-self-attention]]"
  - "[[vaswani-2017-attention-is-all-you-need]]"
  - "[[multi-head-attention]]"
created: 2026-09-16
updated: 2026-09-16
---

# Positional Encoding

由于 [[transformer]] 不含循环与卷积，模型本身无法感知序列顺序，因此必须显式注入序列中 token 的相对或绝对位置信息。论文采用正弦/余弦位置编码，将其相加到编码器与解码器底部的输入嵌入（embedding）上；二者维度相同（d_model = 512）以便相加。

## 公式

```
PE(pos,2i)   = sin(pos / 10000^(2i/d_model))
PE(pos,2i+1) = cos(pos / 10000^(2i/d_model))
```

其中 pos 为位置，i 为维度索引。

## 性质

- 不同维度对应不同频率，波长构成从 2π 到 10000·2π 的几何级数。
- 对任意固定偏移 k，PE(pos+k) 可表示为 PE(pos) 的线性函数，因此模型可能容易学习按相对位置关注，相对位置也可被模型线性表示。

## 选择正弦形式的理由

论文指出，对任意固定偏移 k，PE(pos+k) 可表示为 PE(pos) 的线性函数（见上节性质）。作者选择正弦版本而非 learned positional embeddings，是因为它可能外推到比训练时更长的序列长度。

## 与 learned positional embeddings 的对比

论文也实验了可学习的位置 embedding（Table 3 row E）：

| 方案 | PPL (dev) | BLEU (dev) |
|---|---|---|
| base（正弦） | 4.92 | 25.8 |
| (E) positional embedding instead of sinusoids | 4.92 | 25.7 |

二者结果几乎相同（4.92 PPL / 25.7 BLEU vs base 4.92 / 25.8）。

## 相关页面

- 源论文：[[vaswani-2017-attention-is-all-you-need]]
- 源论文（另一链接形式）：[[vaswani-2017-attention-is-all-you-need]]
- 相关机制：[[self-attention]]、[[multi-head-attention]]、[[why-self-attention]]