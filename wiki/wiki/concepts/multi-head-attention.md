---
type: concept
title: Multi-Head Attention
tags: [attention, transformer, mechanism, representation-learning, architecture-component]
related:
  - "[[transformer]]"
  - "[[self-attention]]"
  - "[[scaled-dot-product-attention]]"
  - "[[attention-visualization]]"
  - "[[注意力可视化与可解释性]]"
  - "[[vaswani-2017-attention-is-all-you-need]]"
created: 2026-09-16
updated: 2026-09-16
---

# Multi-Head Attention

Multi-Head Attention 是 [[transformer]] 的核心机制/组件：将 query（查询）、key（键）、value（值）分别用学习到的线性投影映射到多个子空间（线性投影 h 次），并行执行多次 [[scaled-dot-product-attention]]，再将各头结果拼接并经 `W^O` 投影。

## 公式

```
MultiHead(Q, K, V ) = Concat(head1, ..., headh) W^O
where headi = Attention(Q W^Q_i, K W^K_i, V W^V_i)
```

投影矩阵维度：

```
W^Q_i ∈ R^{dmodel×dk}, W^K_i ∈ R^{dmodel×dk}, W^V_i ∈ R^{dmodel×dv}, W^O ∈ R^{hdv×dmodel}
```

论文中 h = 8，dk = dv = dmodel/h = 64。

## 设计动机

单头注意力通过平均化会抑制有效分辨率；多头允许模型在不同表示子空间的不同位置关注不同信息，从而抵消这一损失。

此外，论文指出相比 ConvS2S（线性）与 ByteNet（对数），Transformer 关联任意两位置所需操作数为常数，代价是有效分辨率下降，用 multi-head attention 抵消。

## 消融结果与实验发现（Table 3）

- 单头注意力比最佳设置差 0.9 BLEU。
- head 过多质量下降（h = 32、dk = 16 时 PPL 5.01 / BLEU 25.4，低于 base 的 4.92 / 25.8）。
- 减小 attention key 维度 dk 损害质量，暗示更复杂的兼容性函数可能有益。

## 功能分化

论文 Figure 5 显示许多头表现出与句子结构相关的行为，不同头明显学会了执行不同任务。Figure 4 中两个头（head 5 与 head 6）似乎参与指代消解。详见 [[注意力可视化与可解释性]]。

## 相关页面

- 源论文：[[vaswani-2017-attention-is-all-you-need]]
- 相关机制：[[self-attention]]、[[scaled-dot-product-attention]]