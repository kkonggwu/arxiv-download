---
type: source
title: "Attention Is All You Need (Vaswani et al., 2017)"
tags: [transformer, attention, machine-translation, sequence-transduction, nlp, architecture, neural-architecture]
related:
  - "[[transformer]]"
  - "[[self-attention]]"
  - "[[multi-head-attention]]"
  - "[[scaled-dot-product-attention]]"
  - "[[positional-encoding]]"
  - "[[encoder-decoder-架构]]"
  - "[[tensor2tensor]]"
  - "[[google-brain]]"
  - "[[wmt-2014-english-german]]"
  - "[[wmt-2014-english-french]]"
  - "[[attention-visualization]]"
  - "[[why-self-attention]]"
  - "[[position-wise-feed-forward-networks逐位置前馈网络]]"
  - "[[注意力可视化与可解释性]]"
  - "[[wmt-2014]]"
  - "[[英语成分句法分析]]"
  - "[[训练配置与正则化]]"
  - "[[自注意力与循环卷积层的比较]]"
  - "[[英法-bleu-41-0-与-41-8-不一致]]"
  - "[[学习率-warmup-调度]]"
  - "[[label-smoothing]]"
authors: [Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, Illia Polosukhin]
year: 2017
url: "https://arxiv.org/abs/1706.03762"
venue: "NIPS 2017"
created: 2026-09-16
updated: 2026-09-16
---

# Attention Is All You Need (Vaswani et al., 2017)

## 概述

本文提出 [[transformer]]，一种完全基于注意力机制、摒弃循环（recurrence）与卷积（convolution）的序列转导（sequence transduction）架构。作者声明这是首个完全依赖 [[self-attention]] 计算输入与输出表示、不使用序列对齐 RNN 或卷积的转导模型。论文发表于 NIPS 2017（Long Beach, CA, USA），arXiv 编号 1706.03762v7。

核心结果：在 WMT 2014 英德任务上达到 28.4 BLEU（big 模型，超越此前最佳含 ensemble 结果 2 BLEU 以上），英法任务上单模型（big）达到 41.8 BLEU，训练 3.5 天 / 8 GPU；并成功迁移到英语成分句法分析。

## 作者与机构

作者来自 Google Brain、Google Research 与 University of Toronto：

- Ashish Vaswani（Google Brain，共同第一作者）
- Noam Shazeer（Google Brain）
- Niki Parmar（Google Research）
- Jakob Uszkoreit（Google Research，提出用 self-attention 替代 RNN）
- Llion Jones（Google Research）
- Aidan N. Gomez（University of Toronto，工作于 Google Brain 期间完成）
- Łukasz Kaiser（Google Brain）
- Illia Polosukhin（工作于 Google Research 期间完成）

致谢对象：Nal Kalchbrenner、Stephan Gouws。

## 核心贡献

- 提出 [[transformer]] 架构，用 [[multi-head-attention]] 与 [[position-wise-feed-forward-networks逐位置前馈网络]] 堆叠构成编码器与解码器，完全替代/去除循环与卷积层。
- 在 WMT 2014 英德任务上达到 28.4 BLEU（big 模型），超越此前最佳（含 ensemble）结果 2 BLEU 以上；base 模型 27.3 BLEU 亦超过所有已发表模型与 ensemble。
- 在 WMT 2014 英法任务上，big 模型达到 41.8 BLEU（Table 2 与摘要），训练成本仅为此前 SOTA 的一小部分。
- 训练效率：base 模型 12 小时 / 8 P100 GPU 即可达到新的翻译质量 SOTA；big 模型 3.5 天 / 8 P100 GPU。
- 将模型成功迁移到英语成分句法分析（English constituency parsing，[[英语成分句法分析]]），在仅 40K 句 WSJ 训练数据下即超过 BerkeleyParser。
- 相比 ConvS2S（线性）与 ByteNet（对数），Transformer 关联任意两位置所需操作数为常数，代价是有效分辨率下降，用 multi-head attention 抵消。

## 模型架构

### 编码器与解码器（整体结构）

[[encoder-decoder-架构]]：编码器与解码器各由 N = 6 层相同子层堆叠而成。每个子层采用残差连接与层归一化（layer normalization）：

```
LayerNorm(x + Sublayer(x))
```

所有子层与嵌入层输出维度 d_model = 512。

- 编码器子层：multi-head self-attention + position-wise feed-forward network。
- 解码器子层：masked multi-head self-attention + encoder-decoder attention + position-wise feed-forward network。解码器采用 auto-regressive 方式生成，额外插入 encoder-decoder attention 子层，并对 self-attention 使用 masking，确保位置 i 的预测只依赖小于 i 的已知输出。

### Scaled Dot-Product Attention

```
Attention(Q, K, V ) = softmax(QK^T / √dk) V   (1)
```

论文指出：当 dk 较大时点积幅值增大，导致 softmax 进入梯度极小的区域，故按 1/√dk 缩放。论文同时对比了 additive attention（Bahdanau et al., 2014）与 dot-product (multiplicative) attention（Luong et al., 2015）。详见 [[scaled-dot-product-attention]]。

### Multi-Head Attention

```
MultiHead(Q, K, V ) = Concat(head1, ..., headh) W^O
where headi = Attention(Q W^Q_i, K W^K_i, V W^V_i)
```

投影矩阵维度：

```
W^Q_i ∈ R^{dmodel×dk}, W^K_i ∈ R^{dmodel×dk}, W^V_i ∈ R^{dmodel×dv}, W^O ∈ R^{hdv×dmodel}
```

详见 [[multi-head-attention]]。

### Position-wise Feed-Forward Networks

```
FFN(x) = max(0, xW1 + b1)W2 + b2   (2)
```

详见 [[position-wise-feed-forward-networks逐位置前馈网络]]。

### 注意力在本模型中的三种应用

1. **编码器-解码器注意力（encoder-decoder attention）**：query 来自解码器，key/value 来自编码器输出。
2. **编码器自注意力（encoder self-attention / intra-attention）**：所有 Q/K/V 来自同一处，即编码器前一层输出。
3. **解码器 masked self-attention**：禁止关注后续位置，保留 auto-regressive 性质。

### Positional Encoding

由于模型不含循环与卷积，需显式注入位置信息。论文采用正弦/余弦函数：

```
PE(pos,2i)   = sin(pos / 10000^(2i/d_model))
PE(pos,2i+1) = cos(pos / 10000^(2i/d_model))
```

正弦/余弦使用不同频率，波长构成从 2π 到 10000·2π 的几何级数；论文指出相对位置可表示为线性函数。与 learned positional embeddings 对比，二者结果几乎相同（Table 3 row E：4.92 PPL / 25.7 BLEU vs base 4.92 / 25.8），选择正弦版本因其可能外推到更长序列。详见 [[positional-encoding]]。

### 超参数

| 参数 | 值 |
|------|-----|
| N（编码器/解码器层数） | 6 |
| dmodel | 512 |
| dff（FFN 内层维度） | 2048 |
| h（注意力头数） | 8 |
| dk = dv | dmodel/h = 64 |

## Why Self-Attention（三项比较标准）

论文以三项标准比较 self-attention、recurrent 与 convolutional 层：每层计算复杂度（per-layer computational complexity）、最少顺序操作数（minimum number of sequential operations）、任意两位置间的最大路径长度（maximum path length between long-range dependencies）。详见 [[自注意力与循环卷积层的比较]] 与 [[why-self-attention]]。

Table 1: Maximum path lengths, per-layer complexity and minimum number of sequential operations for different layer types.

| Layer Type | Complexity per Layer | Sequential Operations | Maximum Path Length |
|---|---|---|---|
| Self-Attention | O(n² · d) | O(1) | O(1) |
| Recurrent | O(n · d²) | O(n) | O(n) |
| Convolutional | O(k · n · d²) | O(1) | O(log_k(n)) |
| Self-Attention (restricted) | O(r · n · d) | O(1) | O(n/r) |

要点：

- Self-attention 层以常数级顺序操作连接所有位置，recurrent 层需 O(n) 顺序操作。
- 当序列长度 n 小于表示维度 d 时，self-attention 比 recurrent 更快（机器翻译中常见）。
- 单层卷积（k < n）无法连接所有输入输出对，需 O(n/k) 层（连续核）或 O(log_k(n)) 层（膨胀卷积）。
- 卷积层通常比 recurrent 层贵 k 倍；可分离卷积降至 O(k·n·d + n·d²)；即使 k = n，可分离卷积复杂度等于 self-attention 层加点式前馈层的组合。
- Restricted self-attention（邻域大小 r）最大路径长度 O(n/r)，论文称留待未来工作。
- 相比 ConvS2S（线性）与 ByteNet（对数），Transformer 关联任意两位置所需操作数为常数，代价是有效分辨率下降，用 Multi-Head Attention 抵消。

## 训练配置

详见 [[训练配置与正则化]]。

- 优化器：Adam，β1 = 0.9，β2 = 0.98，ϵ = 10⁻⁹，warmup_steps = 4000。
- 学习率调度公式 (3)：

```
lrate = d_model^(-0.5) · min(step_num^(-0.5), step_num · warmup_steps^(-1.5))
```

- 正则化：Residual Dropout（base Pdrop = 0.1；英法 big 用 0.1 而非 0.3）、Label Smoothing ϵls = 0.1。
- 批大小：每批约 25000 source tokens 与 25000 target tokens。
- 词表：英德 byte-pair encoding 共享词表约 37000 tokens；英法 word-piece 词表 32000。
- 硬件与调度：8 NVIDIA P100 GPU；base 每步约 0.4 秒，共 100,000 步 / 12 小时；big 每步 1.0 秒，共 300,000 步 / 3.5 天。
- 推理：beam size 4，length penalty α = 0.6；最大输出长度 = 输入长度 + 50（句法分析为 +300，beam size 21，α = 0.3）。
- Checkpoint averaging：base 平均最后 5 个 checkpoint（每 10 分钟写入），big 平均最后 20 个。
- TFLOPS 参考值：K80 = 2.8、K40 = 3.7、M40 = 6.0、P100 = 9.5。

## 数据、任务与资源

- [[wmt-2014]] English-to-German：约 4.5M 句对，byte-pair encoding 共享词表约 37000 tokens。
- [[wmt-2014]] English-to-French：36M 句，word-piece 词表 32000。
- 评测集：newstest2014；开发集：newstest2013。
- 英语成分句法分析：Wall Street Journal (WSJ) portion of Penn Treebank（约 40K 训练句）、BerkleyParser corpora（约 17M 句）、Section 22 / Section 23 of WSJ。
- 代码开源：[[tensor2tensor]]（https://github.com/tensorflow/tensor2tensor）。

## 结果

### 机器翻译

Table 2: The Transformer achieves better BLEU scores than previous state-of-the-art models on the English-to-German and English-to-French newstest2014 tests at a fraction of the training cost.

| Model | BLEU EN-DE | BLEU EN-FR | Cost EN-DE (FLOPs) | Cost EN-FR (FLOPs) |
|---|---|---|---|---|
| ByteNet [18] | 23.75 | | | |
| Deep-Att + PosUnk [39] | | 39.2 | | 1.0 · 10^20 |
| GNMT + RL [38] | 24.6 | 39.92 | 2.3 · 10^19 | 1.4 · 10^20 |
| ConvS2S [9] | 25.16 | 40.46 | 9.6 · 10^18 | 1.5 · 10^20 |
| MoE [32] | 26.03 | 40.56 | 2.0 · 10^19 | 1.2 · 10^20 |
| Deep-Att + PosUnk Ensemble [39] | | 40.4 | | 8.0 · 10^20 |
| GNMT + RL Ensemble [38] | 26.30 | 41.16 | 1.8 · 10^20 | 1.1 · 10^21 |
| ConvS2S Ensemble [9] | 26.36 | 41.29 | 7.7 · 10^19 | 1.2 · 10^21 |
| Transformer (base model) | 27.3 | 38.1 | 3.3 · 10^18 | |
| Transformer (big) | 28.4 | 41.8 | 2.3 · 10^19 | |

训练成本：base 3.3·10^18 FLOPs，big 2.3·10^19 FLOPs。

### 模型变体

Table 3: Variations on the Transformer architecture（英德 newstest2013 dev；perplexity 为 per-wordpiece）。

| 变体 | N | d_model | d_ff | h | d_k | d_v | Pdrop | ϵls | train steps | PPL (dev) | BLEU (dev) | params ×10⁶ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 6 | 512 | 2048 | 8 | 64 | 64 | 0.1 | 0.1 | 100K | 4.92 | 25.8 | 65 |
| (A) | 1 | | | 1 | 512 | 512 | | | | 5.29 | 24.9 | |
| (A) | | | | 4 | 128 | 128 | | | | 5.00 | 25.5 | |
| (A) | | | | 16 | 32 | 32 | | | | 4.91 | 25.8 | |
| (A) | | | | 32 | 16 | 16 | | | | 5.01 | 25.4 | |
| (B) | | | | | 16 | | | | | 5.16 | 25.1 | 58 |
| (B) | | | | | 32 | | | | | 5.01 | 25.4 | 60 |
| (C) | 2 | | | | | | | | | 6.11 | 23.7 | 36 |
| (C) | 4 | | | | | | | | | 5.19 | 25.3 | 50 |
| (C) | 8 | | | | | | | | | 4.88 | 25.5 | 80 |
| (C) | | 256 | | | 32 | 32 | | | | 5.75 | 24.5 | 28 |
| (C) | | 1024 | | | 128 | 128 | | | | 4.66 | 26.0 | 168 |
| (C) | | | 1024 | | | | | | | 5.12 | 25.4 | 53 |
| (C) | | | 4096 | | | | | | | 4.75 | 26.2 | 90 |
| (D) | | | | | | | 0.0 | | | 5.77 | 24.6 | |
| (D) | | | | | | | 0.2 | | | 4.95 | 25.5 | |
| (D) | | | | | | | | 0.0 | | 4.67 | 25.3 | |
| (D) | | | | | | | | 0.2 | | 5.47 | 25.7 | |
| (E) | positional embedding instead of sinusoids | | | | | | | | | 4.92 | 25.7 | |
| big | 6 | 1024 | 4096 | 16 | | | 0.3 | | 300K | 4.33 | 26.4 | 213 |

模型变体关键发现：

- 单头注意力比最佳设置差 0.9 BLEU；head 过多质量下降。
- 减小 attention key 维度 dk 损害质量，暗示更复杂的兼容性函数可能有益。
- 更大模型更好；dropout 对避免过拟合非常有帮助。
- Label smoothing 损害 perplexity 但提升 accuracy 与 BLEU。
- 正弦位置编码与 learned positional embeddings 结果几乎相同（row E：4.92 PPL / 25.7 BLEU vs base 4.92 / 25.8）；选择正弦版本因其可能外推到更长序列（详见 Positional Encoding）。

### 英语成分句法分析

Table 4: The Transformer generalizes well to English constituency parsing（WSJ Section 23 F1）。

| Parser | Training | WSJ 23 F1 |
|---|---|---|
| Vinyals & Kaiser el al. (2014) [37] | WSJ only, discriminative | 88.3 |
| Petrov et al. (2006) [29] | WSJ only, discriminative | 90.4 |
| Zhu et al. (2013) [40] | WSJ only, discriminative | 90.4 |
| Dyer et al. (2016) [8] | WSJ only, discriminative | 91.7 |
| Transformer (4 layers) | WSJ only, discriminative | 91.3 |
| Zhu et al. (2013) [40] | semi-supervised | 91.3 |
| Huang & Harper (2009) [14] | semi-supervised | 91.3 |
| McClosky et al. (2006) [26] | semi-supervised | 92.1 |
| Vinyals & Kaiser el al. (2014) [37] | semi-supervised | 92.1 |
| Transformer (4 layers) | semi-supervised | 92.7 |
| Luong et al. (2015) [23] | multi-task | 93.0 |
| Dyer et al. (2016) [8] | generative | 93.3 |

4 层 Transformer 在 WSJ only 设置下达到 91.3 F1，semi-supervised 设置下 92.7 F1；在仅 40K 句 WSJ 训练数据下即超过 BerkeleyParser。

> [!note] 来源版本差异
> 新生成的来源版本进一步表述为「优于所有此前模型（除 Recurrent Neural Network Grammar 的 93.3）」；磁盘上的既有版本未作这一概括，仅记录 4 层 Transformer 的两项 F1 数值与「超过 BerkeleyParser」。

## 注意力可视化与可解释性（Figure 3–5）

详见 [[注意力可视化与可解释性]]。论文以定性可视化展示注意力可解释性，均取自 6 层编码器中的第 5 层 self-attention，不同颜色代表不同头：

- Figure 3：多个注意力头关注动词 "making" 的长距离依存，补全 "making...more difficult" 短语。
- Figure 4：两个头（head 5 与 head 6）似乎参与指代消解（anaphora resolution），对 "its" 的注意力非常尖锐（sharp）。
- Figure 5：许多头表现出与句子结构相关的行为，不同头明显学会了执行不同任务。

这些图支持论文关于多头注意力可学习不同子任务、并能捕获长距离依存与句法/指代结构的论断，但属于定性示例而非定量评测。

## 对比系统

ByteNet、Deep-Att + PosUnk、GNMT + RL、ConvS2S、MoE、Recurrent Neural Network Grammar、BerkeleyParser、Vinyals & Kaiser et al. (2014)、Petrov et al. (2006)、Zhu et al. (2013)、Huang & Harper (2009)、McClosky et al. (2006)、Luong et al. (2015)。

## 结论与未来工作

- Transformer 是首个完全基于 attention 的序列转导模型，可显著更快训练。
- 计划扩展到文本以外模态（图像、音频、视频）。
- 计划研究受限注意力机制（restricted self-attention，邻域大小 r）以高效处理大输入输出。
- 计划探索生成更少顺序操作的模型。
- 代码开源地址：https://github.com/tensorflow/tensor2tensor（见 [[tensor2tensor]]）。

## 论文内部数值不一致

> [!warning] 来源内部矛盾
> 英法 big 模型 BLEU：Table 2 与摘要记为 **41.8**，但第 6.1 节正文写 "our big model achieves a BLEU score of 41.0"。同一论文内部数值不一致（41.0 vs 41.8）。两个来源版本均记录了这一矛盾，未做统一。详见 [[英法-bleu-41-0-与-41-8-不一致]]。
>
> 新生成的来源版本补充指出：该差异是笔误还是不同配置（如 dropout 0.1 vs 0.3）尚不明确。

## 知识谱系（参考文献 [5]–[40]）

参考文献系统性暴露了 Transformer 的知识谱系：

- 序列到序列学习：Sutskever et al. 2014、Cho et al. 2014。
- 注意力机制：Bahdanau et al. 2014、Luong et al. 2015、Parikh et al. 2016、Kim et al. 2017、Lin et al. 2017。
- 卷积序列模型：Gehring et al. 2017（ConvS2S）、Kalchbrenner et al. 2017（ByteNet）、Chollet 2016（Xception）。
- 循环网络与 LSTM：Hochreiter & Schmidhuber 1997、Chung et al. 2014、Graves 2013。
- 优化与正则化：Kingma & Ba 2015（Adam）、Srivastava et al. 2014（Dropout）、Ba et al. 2016（Layer Normalization）、He et al. 2016（残差学习）。
- 子词与词表处理：Sennrich et al. 2015（BPE / subword units）、Press & Wolf 2016。
- MoE：Shazeer et al. 2017（Sparsely-Gated Mixture-of-Experts）。
- 记忆网络：Sukhbaatar et al. 2015、Kaiser & Bengio 2016、Kaiser & Sutskever 2016。
- 句法分析：Vinyals & Kaiser et al. 2015、Dyer et al. 2016（Recurrent Neural Network Grammars）、Zhu et al. 2013、McClosky et al. 2006、Petrov et al. 2006、Huang & Harper 2009。
- Google NMT 系统：Wu et al. 2016。

## 开放问题

- 注意力可视化仅为定性示例，缺乏头分工普遍性的定量证据；论文未对注意力可解释性做消融或定量指标。
- 参考文献中 MoE、记忆网络、结构化注意力等与 Transformer 的关系未在正文展开对比。
- 受限 self-attention（邻域 r）的具体实现与效果留待未来工作。
- 更复杂兼容性函数（替代点积）的探索方向。
- 扩展到图像、音频、视频等非文本模态的具体方案。
- 论文未给出与 RNN 在长序列上的系统性对比数据（仅定性论述）。