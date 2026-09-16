---
type: concept
title: Self-attention
tags: [attention, transformer, mechanism, sequence-modeling]
related:
  - "[[transformer]]"
  - "[[multi-head-attention]]"
  - "[[scaled-dot-product-attention]]"
  - "[[why-self-attention]]"
  - "[[encoder-decoder-架构]]"
  - "[[自注意力与循环卷积层的比较]]"
  - "[[vaswani-2017-attention-is-all-you-need]]"
  - "[[attention-visualization]]"
  - "[[注意力可视化与可解释性]]"
  - "[[positional-encoding]]"
created: 2026-09-16
updated: 2026-09-16
---

# Self-attention

Self-attention（亦称 intra-attention）是一种将单个序列中不同位置相互关联以计算该序列表示的注意力机制。它是 [[transformer]] 的核心组件，被用于编码器与解码器的每一层。

> [!note] 版本差异标注
> 下文中 `（现有版本）` 指磁盘上已有版本，`（新生成版本）` 指由 `2017 - Vaswani et al. - Attention Is All You Need [1706.03762].pdf` 新生成的版本。凡两版本表述不同或仅一方提及的内容，均分别标注。

## 在 Transformer 中的应用

| 类型 | 查询 / 键 / 值的来源 | 说明 |
|---|---|---|
| Encoder self-attention | 同一处（自注意力） | 编码器内部各位置相互关注（现有版本）。所有 Q/K/V 均来自同一处，即编码器前一层的输出，每个位置可关注前一层所有位置（新生成版本）。 |
| Decoder masked self-attention | 同一处（自注意力），带掩码 | 解码器内部使用 masking 防止位置关注后续位置，以保持 auto-regressive 解码（现有版本）。通过 masking 禁止关注未来位置，确保位置 i 的预测只依赖小于 i 的已知输出（新生成版本）。 |
| Encoder-decoder attention | 查询来自解码器，键与值来自编码器输出 | 严格说属于 cross-attention。**此第三种应用仅见于现有版本**。 |

## 复杂度与路径长度

论文以三项标准（每层计算复杂度、顺序操作数、最大路径长度）比较 self-attention 与 recurrent、convolutional 层：现有版本参见 [[why-self-attention]]；新生成版本参见 [[自注意力与循环卷积层的比较]]。

| Layer Type | Complexity per Layer | Sequential Operations | Maximum Path Length |
|---|---|---|---|
| Self-Attention | O(n² · d) | O(1) | O(1) |
| Recurrent | O(n · d²) | O(n) | O(n) |
| Convolutional | O(k · n · d²) | O(1) | O(log_k(n)) |
| Self-Attention (restricted) | O(r · n · d) | O(1) | O(n/r) |

关键论点：

- Self-attention 层以常数级顺序操作连接所有位置；recurrent 层需 O(n) 顺序操作。当序列长度 n 小于表示维度 d 时，self-attention 比 recurrent 层更快（机器翻译中常见）。（两个版本均支持）
- 单层卷积（k < n）无法连接所有输入输出对，需 O(n/k) 层（连续核）或 O(log_k(n)) 层（膨胀卷积）。（新生成版本）
- 相比 ConvS2S（线性）与 ByteNet（对数），Transformer 关联任意两位置所需操作数为常数，代价是有效分辨率下降，用 [[multi-head-attention]] 抵消。（新生成版本）

## 可解释性证据

论文 Figure 3–5 以定性可视化展示编码器第 5 层 self-attention 的可解释性：

- （现有版本）称其可捕获长距离依存、指代消解与句法结构；详见 [[attention-visualization]]。
- （新生成版本）补充具体示例：多个头可捕获长距离依存（"making...more difficult"）、参与指代消解（"its"）并表现出与句法结构相关的行为，但均为定性示例；详见 [[注意力可视化与可解释性]]。

## 未来方向

论文提出受限 self-attention（restricted self-attention，邻域大小 r，最大路径长度 O(n/r)）作为未来工作方向。（新生成版本；该受限变体同时作为一行出现在上文的复杂度对比表中）

## 相关页面

- 源论文：
  - 现有版本：[[vaswani-2017-attention-is-all-you-need]]
  - 新生成版本：[[vaswani-2017-attention-is-all-you-need]]
- 相关机制：[[transformer]]、[[multi-head-attention]]、[[scaled-dot-product-attention]]、[[positional-encoding]]
- 对比与解释：[[why-self-attention]]、[[自注意力与循环卷积层的比较]]、[[attention-visualization]]、[[注意力可视化与可解释性]]
- 架构：[[encoder-decoder-架构]]（现有版本）