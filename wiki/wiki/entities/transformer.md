---
type: entity
title: Transformer
tags: [architecture, attention, sequence-transduction, nlp, model, model-architecture]
related:
  - "[[self-attention]]"
  - "[[multi-head-attention]]"
  - "[[scaled-dot-product-attention]]"
  - "[[positional-encoding]]"
  - "[[encoder-decoder-架构]]"
  - "[[position-wise-feed-forward-networks逐位置前馈网络]]"
  - "[[tensor2tensor]]"
  - "[[why-self-attention]]"
  - "[[attention-visualization]]"
  - "[[vaswani-2017-attention-is-all-you-need]]"
created: 2026-09-16
updated: 2026-09-16
---

# Transformer

Transformer 是 Vaswani et al. (2017) 在《Attention Is All You Need》中提出的序列转导模型架构，完全基于注意力机制，摒弃循环与卷积。论文声明它是首个完全依赖 [[self-attention]] 计算输入输出表示、不使用序列对齐 RNN 或卷积的转导模型。

## 架构组成

- [[encoder-decoder-架构]]：编码器与解码器各由 N = 6 层堆叠构成，每个子层输出为 `LayerNorm(x + Sublayer(x))`。
- [[scaled-dot-product-attention]]：核心注意力计算单元。
- [[multi-head-attention]]：并行多头注意力，抵消单头平均化带来的分辨率损失。
- [[position-wise-feed-forward-networks逐位置前馈网络]]：每个位置独立的两层前馈网络。
- [[positional-encoding]]：正弦/余弦位置编码，为无循环结构注入顺序信息。

## 注意力在本模型中的三种应用

1. Encoder-decoder attention：解码器查询编码器输出。
2. Encoder self-attention：编码器内部自注意力。
3. Masked self-attention：解码器自注意力，配合掩码保持 auto-regressive 性质。

## 关键超参数

| 参数 | base | big |
|------|------|-----|
| N | 6 | 6 |
| dmodel | 512 | 1024 |
| dff | 2048 | 4096 |
| h | 8 | 16 |
| dk = dv | 64 | — |
| Pdrop | 0.1 | 0.3 |
| 训练步数 | 100K | 300K |
| 参数量 | 65M | 213M |

## 效率特性

论文以三项标准比较层类型：per-layer computational complexity、minimum number of sequential operations、maximum path length between long-range dependencies。Self-attention 层以 O(1) 顺序操作连接所有位置，最大路径长度 O(1)；recurrent 层需 O(n) 顺序操作、路径长度 O(n)。当序列长度 n 小于表示维度 d 时，self-attention 比 recurrent 更快。

## 实验结果

- 英德 newstest2014：base 27.3 BLEU，big 28.4 BLEU（超越此前最佳含 ensemble 结果 2 BLEU 以上）。
- 英法 newstest2014：base 38.1 BLEU，big 41.8 BLEU（正文一处写 41.0，见 [[vaswani-2017-attention-is-all-you-need]] 中的内部数值不一致说明）。
- 训练成本：base 3.3·10^18 FLOPs，big 2.3·10^19 FLOPs。
- 英语成分句法分析：4 层 Transformer 在 WSJ only 下 91.3 F1，semi-supervised 下 92.7 F1。

## 实现与后续方向

代码开源地址为 https://github.com/tensorflow/tensor2tensor（[[tensor2tensor]]）。论文计划扩展到文本以外模态（图像、音频、视频）与受限注意力机制。
