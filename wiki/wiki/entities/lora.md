---
type: entity
title: LoRA (Low-Rank Adaptation)
tags: [parameter-efficient-fine-tuning, low-rank-adaptation, microsoft, transformer, gpt-3]
related:
  - "[[hu-2021-lora]]"
  - "[[low-rank-adaptation]]"
  - "[[adapter-layers]]"
  - "[[prefix-tuning]]"
  - "[[bitfit]]"
  - "[[parameter-efficient-adaptation]]"
  - "[[gpt-3]]"
  - "[[gpt-2]]"
  - "[[roberta]]"
  - "[[deberta]]"
  - "[[glue-benchmark]]"
  - "[[wikisql]]"
  - "[[samsum]]"
  - "[[e2e-nlg]]"
  - "[[huggingface-transformers]]"
  - "[[nvidia-v100]]"
  - "[[which-weight-matrices-to-apply-lora]]"
  - "[[optimal-lora-rank]]"
created: 2026-09-16
updated: 2026-09-16
---

# LoRA (Low-Rank Adaptation)

## 概述

LoRA（Low-Rank Adaptation，低秩适配）是 Hu et al. (2021) 在论文《LoRA: Low-Rank Adaptation of Large Language Models》（arXiv:2106.09685v2）中提出的一种参数高效适配（parameter-efficient adaptation）方法。其核心思想是：**冻结预训练模型权重，向 Transformer 各层注入可训练的低秩分解矩阵**，从而以极少的可训练参数完成下游任务适配，同时不引入额外推理延迟。

LoRA 由 Microsoft Corporation 发布，作者包括 Edward Hu、Yelong Shen、Phillip Wallis、Zeyuan Allen-Zhu、Yuanzhi Li、Shean Wang、Lu Wang、Weizhu Chen，官方实现托管于 GitHub 仓库 `microsoft/LoRA`。

## 方法

### 核心公式

对于预训练权重矩阵 $W_0 \in \mathbb{R}^{d \times k}$，LoRA 将其更新约束为低秩分解：

$$W_0 + \Delta W = W_0 + BA$$

其中 $B \in \mathbb{R}^{d \times r}$，$A \in \mathbb{R}^{r \times k}$，秩 $r \ll \min(d, k)$。

修改后的前向传播为：

$$h = W_0 x + \Delta W x = W_0 x + BAx$$

### 初始化与缩放

- $A$ 使用随机高斯初始化，$B$ 初始化为零，因此训练开始时 $\Delta W = BA = 0$，模型行为与预训练模型完全一致。
- $\Delta W x$ 按 $\alpha / r$ 缩放，其中 $\alpha$ 取首次尝试的 $r$ 值且不进行调参。

### 训练目标

- 全量微调目标：$\max_\Phi \sum_{(x,y) \in Z} \sum_{t=1}^{|y|} \log(P_\Phi(y_t \mid x, y_{<t}))$
- LoRA 目标：$\max_\Theta \sum_{(x,y) \in Z} \sum_{t=1}^{|y|} \log p_{\Phi_0 + \Delta\Phi(\Theta)}(y_t \mid x, y_{<t})$

其中 $|\Theta| \ll |\Phi_0|$，LoRA 用更小的参数集 $\Theta$ 编码更新量 $\Delta\Phi = \Delta\Phi(\Theta)$。

### 在 Transformer 中的应用

LoRA 仅适配自注意力投影矩阵中的 $W_q$ 与 $W_v$，冻结 MLP 模块。MLP、LayerNorm 与 bias 的适配留作未来工作。可训练参数量为：

$$|\Theta| = 2 \times \hat{L}_{\text{LoRA}} \times d_{\text{model}} \times r$$

## 关键优势

1. **参数效率**：相比用 Adam 微调的 GPT-3 175B，LoRA 可将可训练参数量减少约 10,000 倍，GPU 显存需求减少 3 倍。GPT-3 175B 场景下 $|\Theta|$ 可小至 $|\Phi_0|$ 的 0.01%。
2. **无额外推理延迟**：部署时可将 $W = W_0 + BA$ 合并，推理路径与原始模型完全一致。
3. **显存与存储收益**：Adam 训练下 VRAM 减少最多 2/3；GPT-3 175B 训练显存从 1.2TB 降至 350GB；$r=4$ 且仅适配 $W_q$/$W_v$ 时 checkpoint 从 350GB 降至 35MB（约 10,000×）。
4. **训练加速**：GPT-3 175B 相比全量微调约 25% 加速（32.5 → 43.1 tokens/s per V100 GPU）。
5. **任务切换灵活**：可共享同一预训练模型，按任务替换 $A$/$B$ 矩阵。
6. **正交可组合**：与 prefix-tuning 等方法正交，可组合使用（见论文 Appendix E）。

## 推理延迟对比

Table 1（GPT-2 medium 单次前向推理延迟，毫秒，NVIDIA Quadro RTX8000，100 次试验平均）：

| Batch Size | 32 | 16 | 1 |
|---|---|---|---|
| Sequence Length | 512 | 256 | 128 |
| \|Θ\| | 0.5M | 11M | 11M |
| Fine-Tune/LoRA | 1449.4±0.8 | 338.0±0.6 | 19.8±2.7 |
| AdapterL | 1482.0±1.0 (+2.2%) | 354.8±0.5 (+5.0%) | 23.9±2.1 (+20.7%) |
| AdapterH | 1492.2±1.0 (+3.0%) | 366.3±0.5 (+8.4%) | 25.8±2.2 (+30.3%) |

LoRA 与全量微调的延迟一致，而 adapter 层在在线、短序列、batch size=1 场景下引入显著延迟。

## 实证结果

LoRA 在 RoBERTa、DeBERTa、GPT-2、GPT-3 上质量持平或优于全量微调：

- **GPT-3 175B**：以 4.7M 可训练参数（vs 全量微调 175,255.8M）在 WikiSQL（73.4 vs 73.8）、MNLI-m（91.7 vs 89.5）、SAMSum（53.8/29.8/45.9 vs 52.0/28.0/44.5）上匹配或超越全量微调。
- **GLUE**：RoBERTa base (LoRA) 以 0.3M 参数达到平均 87.2，与全量微调持平。
- 并非所有方法都随可训练参数增加而单调提升（Figure 2）。

## 局限

- 若将 $A$、$B$ 合并进 $W$ 以消除推理延迟，则难以在单次前向中对不同任务（不同 $A$、$B$）的输入进行批处理。
- 延迟不敏感场景可选择不合并、动态选择 LoRA 模块。

## 术语约定

- $d_{\text{model}}$：Transformer 层输入/输出维度
- $W_q$、$W_k$、$W_v$、$W_o$：自注意力投影矩阵
- $W$ 或 $W_0$：预训练权重；$\Delta W$：适配期间的累积梯度更新
- $r$：LoRA 模块秩
- MLP 前馈维度 $d_{\text{ffn}} = 4 \times d_{\text{model}}$
- 优化器：Adam

## 相关页面

- 来源论文：[[hu-2021-lora]]
- 核心概念：[[low-rank-adaptation]]、[[parameter-efficient-adaptation]]
- 对比方法：[[adapter-layers]]、[[prefix-tuning]]、[[bitfit]]
- 评测模型与数据集：[[gpt-3]]、[[gpt-2]]、[[roberta]]、[[deberta]]、[[glue-benchmark]]、[[wikisql]]、[[samsum]]、[[e2e-nlg]]
- 工具与硬件：[[huggingface-transformers]]、[[nvidia-v100]]
- 开放问题：[[which-weight-matrices-to-apply-lora]]、[[optimal-lora-rank]]