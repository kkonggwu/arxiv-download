---
type: source
title: "LoRA: Low-Rank Adaptation of Large Language Models (Hu et al., 2021)"
tags: [lora, parameter-efficient-adaptation, low-rank, fine-tuning, transformer, gpt-3, microsoft]
related:
  - "[[lora]]"
  - "[[low-rank-adaptation]]"
  - "[[parameter-efficient-adaptation]]"
  - "[[adapter-layers]]"
  - "[[prefix-tuning]]"
  - "[[intrinsic-rank]]"
  - "[[subspace-similarity]]"
  - "[[amplification-factor]]"
  - "[[gpt-3]]"
  - "[[gpt-2]]"
  - "[[roberta]]"
  - "[[deberta]]"
  - "[[glue-benchmark]]"
  - "[[wikisql]]"
  - "[[mnli]]"
  - "[[e2e-nlg]]"
  - "[[samsum]]"
  - "[[webnlg]]"
  - "[[dart]]"
  - "[[microsoft]]"
  - "[[huggingface-transformers]]"
  - "[[nvidia-v100]]"
  - "[[nvidia-quadro-rtx8000]]"
  - "[[compacter]]"
  - "[[bitfit]]"
  - "[[prompt-tuning]]"
  - "[[adapterfusion]]"
  - "[[adapterdrop]]"
  - "[[megatron-lm]]"
  - "[[gshard]]"
  - "[[which-weight-matrices-to-apply-lora]]"
  - "[[optimal-lora-rank]]"
  - "[[why-do-more-special-tokens-hurt-prefix-tuning]]"
  - "[[how-to-principledly-select-weight-matrices-for-lora]]"
  - "[[is-w-rank-deficient]]"
  - "[[how-does-fine-tuning-transform-pretrained-features]]"
authors: [Edward Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, Weizhu Chen]
year: 2021
url: "https://arxiv.org/abs/2106.09685"
venue: "arXiv:2106.09685v2"
created: 2026-09-16
updated: 2026-09-16
---

# LoRA: Low-Rank Adaptation of Large Language Models (Hu et al., 2021)

## 一句话总结

论文提出 [[low-rank-adaptation]]（LoRA）：冻结预训练权重，向 Transformer 各层注入可训练的低秩分解矩阵 `W0 + BA`，从而在 GPT-3 175B 上把可训练参数量减少约 10,000 倍、GPU 显存需求减少约 3 倍，且部署时无额外推理延迟。

## 基本信息

- 作者：Edward Hu、Yelong Shen、Phillip Wallis、Zeyuan Allen-Zhu、Yuanzhi Li、Shean Wang、Lu Wang、Weizhu Chen（[[microsoft]]）
- 版本：arXiv:2106.09685v2
- 代码：GitHub 仓库 `microsoft/LoRA`
- 实验硬件：[[nvidia-v100]]（全部实验）、[[nvidia-quadro-rtx8000]]（推理延迟实验，100 次试验平均）
- 工具：[[pytorch]]、[[huggingface-transformers]]、Adam / AdamW

## 问题陈述

给定预训练自回归语言模型 `PΦ(y|x)` 与下游任务数据集 `Z = {(xi, yi)}`，全量微调学习 `∆Φ` 且 `|∆Φ| = |Φ0|`。LoRA 用更小的参数集 `Θ` 编码 `∆Φ = ∆Φ(Θ)`，满足 `|Θ| ≪ |Φ0|`。

全量微调目标：

```
max_Φ Σ_{(x,y)∈Z} Σ_{t=1}^{|y|} log(PΦ(yt | x, y<t))
```

LoRA 目标：

```
max_Θ Σ_{(x,y)∈Z} Σ_{t=1}^{|y|} log p_{Φ0+∆Φ(Θ)}(yt | x, y<t)
```

## 方法

修改后的前向传播：

```
h = W0x + ∆Wx = W0x + BAx
```

其中 `B ∈ R^{d×r}`、`A ∈ R^{r×k}`，`r ≪ min(d,k)`。`A` 用随机高斯初始化，`B` 初始化为零，因此训练开始时 `∆W = BA = 0`。`∆Wx` 按 `α/r` 缩放，`α` 取首次尝试的 `r` 且不调参。

术语约定：`d_model` 为 Transformer 层输入/输出维度；`Wq`、`Wk`、`Wv`、`Wo` 为自注意力投影矩阵；`W` 或 `W0` 为预训练权重，`∆W` 为适配期间的累积梯度更新；`r` 为 LoRA 模块秩；MLP 前馈维度 `d_ffn = 4 × d_model`。

### 应用策略

- 仅适配注意力权重 `Wq`、`Wv`，冻结 MLP 模块；MLP / LayerNorm / bias 的适配留作未来工作。
- 部署时可合并 `W = W0 + BA`，无额外推理延迟。
- 与 prefix-tuning 等方法正交，可组合（见 Appendix E）。

### 各方法可训练参数计数公式

- PreEmbed：`|Θ| = d_model × (lp + li)`
- PreLayer：`|Θ| = L × d_model × (lp + li)`
- Adapter：`|Θ| = L̂_Adpt × (2 × d_model × r + r + d_model) + 2 × L̂_LN × d_model`
- LoRA：`|Θ| = 2 × L̂_LoRA × d_model × r`

## 对现有方案的批评

- adapter 层引入推理延迟（尤其在线、短序列、batch size=1 场景），且难以绕过额外计算。
- prefix tuning 难以优化、性能随可训练参数非单调变化，并占用序列长度。

### Table 1：GPT-2 medium 单次前向推理延迟（毫秒，NVIDIA Quadro RTX8000，100 次平均）

| Batch Size | 32 | 16 | 1 |
|---|---|---|---|
| Sequence Length | 512 | 256 | 128 |
| \|Θ\| | 0.5M | 11M | 11M |
| Fine-Tune/LoRA | 1449.4±0.8 | 338.0±0.6 | 19.8±2.7 |
| AdapterL | 1482.0±1.0 (+2.2%) | 354.8±0.5 (+5.0%) | 23.9±2.1 (+20.7%) |
| AdapterH | 1492.2±1.0 (+3.0%) | 366.3±0.5 (+8.4%) | 25.8±2.2 (+30.3%) |

## 实证结果

### 主要量化收益

- 相比用 Adam 微调的 GPT-3 175B，可训练参数量减少 10,000 倍、GPU 显存需求减少 3 倍。
- GPT-3 175B 场景下 `|Θ|` 可小至 `|Φ0|` 的 0.01%。
- Adam 训练下 VRAM 减少最多 2/3；GPT-3 175B 训练显存从 1.2TB 降至 350GB。
- `r=4` 且仅适配 `Wq`/`Wv` 时 checkpoint 从 350GB 降至 35MB（约 10,000×）。
- GPT-3 175B 相比全量微调约 25% 训练加速（32.5 → 43.1 tokens/s per V100 GPU）。

### Table 2：GLUE（RoBERTa base/large、DeBERTa XXL）

- RoBERTa base (LoRA) 0.3M 平均 87.2 vs FT 86.4
- RoBERTa large (LoRA) 0.8M 平均 89.0 vs FT 88.9
- DeBERTa XXL (LoRA) 4.7M 平均 91.3 vs FT 91.1

### Table 3：E2E NLG Challenge（GPT-2 M/L）

- GPT-2 M (LoRA) 0.35M BLEU 70.4 vs FT 68.2
- GPT-2 L (LoRA) 0.77M BLEU 70.4 vs FT 68.5

### Table 4：GPT-3 175B

LoRA 以 4.7M 可训练参数（vs FT 175,255.8M）在 WikiSQL (73.4 vs 73.8)、MNLI-m (91.7 vs 89.5)、SAMSum (53.8/29.8/45.9 vs 52.0/28.0/44.5) 上匹配或超越全量微调。

### Table 5：GPT-3 175B，18M 可训练参数（WikiSQL ±0.5% / MultiNLI ±0.1%）

| Weight Type | Wq | Wk | Wv | Wo | Wq,Wk | Wq,Wv | Wq,Wk,Wv,Wo |
|---|---|---|---|---|---|---|---|
| Rank r | 8 | 8 | 8 | 8 | 4 | 4 | 2 |
| WikiSQL | 70.4 | 70.0 | 73.0 | 73.2 | 71.4 | 73.7 | 73.7 |
| MultiNLI | 91.0 | 90.8 | 91.0 | 91.3 | 91.3 | 91.3 | 91.7 |

### Table 6：不同秩 r 的验证准确率

| Weight Type | r=1 | r=2 | r=4 | r=8 | r=64 |
|---|---|---|---|---|---|
| WikiSQL Wq | 68.8 | 69.6 | 70.5 | 70.4 | 70.0 |
| WikiSQL Wq,Wv | 73.4 | 73.3 | 73.7 | 73.8 | 73.5 |
| WikiSQL Wq,Wk,Wv,Wo | 74.1 | 73.7 | 74.0 | 74.0 | 73.9 |
| MultiNLI Wq | 90.7 | 90.9 | 91.1 | 90.7 | 90.7 |
| MultiNLI Wq,Wv | 91.3 | 91.4 | 91.3 | 91.6 | 91.4 |
| MultiNLI Wq,Wk,Wv,Wo | 91.2 | 91.7 | 91.7 | 91.5 | 91.4 |

### Table 7：GPT-3 第 48 层 Frobenius 范数

| | r=4 ∆Wq | r=4 Wq | r=4 Random | r=64 ∆Wq | r=64 Wq | r=64 Random |
|---|---|---|---|---|---|---|
| ‖U^>WqV^>‖_F | 0.32 | 21.67 | 0.02 | 1.90 | 37.71 | 0.33 |

`‖Wq‖_F = 61.95`；`r=4` 时 `‖∆Wq‖_F = 6.91`；`r=64` 时 `‖∆Wq‖_F = 3.57`。

### Table 8：微调显著优于 few-shot（GPT-3）

| Method | MNLI-m (Val. Acc./%) | RTE (Val. Acc./%) |
|---|---|---|
| GPT-3 Few-Shot | 40.6 | 69.0 |
| GPT-3 Fine-Tuned | 89.5 | 85.4 |

### Table 12：GPT-3 各适配方法训练超参数

| Hyperparameters | Fine-Tune | PreEmbed | PreLayer | BitFit | AdapterH | LoRA |
|---|---|---|---|---|---|---|
| Optimizer | AdamW | | | | | |
| Batch Size | 128 | | | | | |
| # Epoch | 2 | | | | | |
| Warmup Tokens | 250,000 | | | | | |
| LR Schedule | Linear | | | | | |
| Learning Rate | 5.00E-06 | 5.00E-04 | 1.00E-04 | 1.6E-03 | 1.00E-04 | 2.00E-04 |

### Table 13：GPT-2 各方法在 DART 上的结果

| Method | # Trainable Parameters | DART BLEU↑ | MET↑ | TER↓ |
|---|---|---|---|---|
| GPT-2 Medium Fine-Tune | 354M | 46.2 | 0.39 | 0.46 |
| AdapterL | 0.37M | 42.4 | 0.36 | 0.48 |
| AdapterL | 11M | 45.2 | 0.38 | 0.46 |
| FTTop2 | 24M | 41.0 | 0.34 | 0.56 |
| PrefLayer | 0.35M | 46.4 | 0.38 | 0.46 |
| LoRA | 0.35M | 47.1±.2 | 0.39 | 0.46 |
| GPT-2 Large Fine-Tune | 774M | 47.0 | 0.39 | 0.46 |
| AdapterL | 0.88M | 45.7±.1 | 0.38 | 0.46 |
| AdapterL | 23M | 47.1±.1 | 0.39 | 0.45 |
| PrefLayer | 0.77M | 46.7 | 0.38 | 0.45 |
| LoRA | 0.77M | 47.5±.1 | 0.39 | 0.45 |

### Table 14：GPT-2 各方法在 WebNLG 上的结果（U=unseen, S=seen, A=all）

| Method | BLEU U | BLEU S | BLEU A | MET U | MET S | MET A | TER U | TER S | TER A |
|---|---|---|---|---|---|---|---|---|---|
| GPT-2 Medium Fine-Tune (354M) | 27.7 | 64.2 | 46.5 | .30 | .45 | .38 | .76 | .33 | .53 |
| AdapterL (0.37M) | 45.1 | 54.5 | 50.2 | .36 | .39 | .38 | .46 | .40 | .43 |
| AdapterL (11M) | 48.3 | 60.4 | 54.9 | .38 | .43 | .41 | .45 | .35 | .39 |
| FTTop2 (24M) | 18.9 | 53.6 | 36.0 | .23 | .38 | .31 | .99 | .49 | .72 |
| Prefix (0.35M) | 45.6 | 62.9 | 55.1 | .38 | .44 | .41 | .49 | .35 | .40 |
| LoRA (0.35M) | 46.7±.4 | 62.1±.2 | 55.3±.2 | .38 | .44 | .41 | .46 | .33 | .39 |
| GPT-2 Large Fine-Tune (774M) | 43.1 | 65.3 | 55.5 | .38 | .46 | .42 | .53 | .33 | .42 |
| AdapterL (0.88M) | 49.8±.0 | 61.1±.0 | 56.0±.0 | .38 | .43 | .41 | .44 | .35 | .39 |
| AdapterL (23M) | 49.2±.1 | 64.7±.2 | 57.7±.1 | .39 | .46 | .43 | .46 | .33 | .39 |
| Prefix (0.77M) | 47.7 | 63.4 | 56.3 | .39 | .45 | .42 | .48 | .34 | .40 |
| LoRA (0.77M) | 48.4±.3 | 64.0±.3 | 57.0±.1 | .39 | .45 | .42 | .45 | .32 | .38 |

### Table 15：不同适配方法在 WikiSQL 与 MNLI 上的超参数分析（验证准确率）

| Method | Hyperparameters | # Trainable Parameters | WikiSQL | MNLI-m |
|---|---|---|---|---|
| Fine-Tune | - | 175B | 73.8 | 89.5 |
| PrefixEmbed | lp = 32, li = 8 | 0.4 M | 55.9 | 84.9 |
| PrefixEmbed | lp = 64, li = 8 | 0.9 M | 58.7 | 88.1 |
| PrefixEmbed | lp = 128, li = 8 | 1.7 M | 60.6 | 88.0 |
| PrefixEmbed | lp = 256, li = 8 | 3.2 M | 63.1 | 88.6 |
| PrefixEmbed | lp = 512, li = 8 | 6.4 M | 55.9 | 85.8 |
| PrefixLayer | lp = 2, li = 2 | 5.1 M | 68.5 | 89.2 |
| PrefixLayer | lp = 8, li = 0 | 10.1 M | 69.8 | 88.2 |
| PrefixLayer | lp = 8, li = 8 | 20.2 M | 70.1 | 89.5 |
| PrefixLayer | lp = 32, li = 4 | 44.1 M | 66.4 | 89.6 |
| PrefixLayer | lp = 64, li = 0 | 76.1 M | 64.9 | 87.9 |
| AdapterH | r = 1 | 7.1 M | 71.9 | 89.8 |
| AdapterH | r = 4 | 21.2 M | 73.2 | 91.0 |
| AdapterH | r = 8 | 40.1 M | 73.2 | 91.5 |
| AdapterH | r = 16 | 77.9 M | 73.2 | 91.5 |
| AdapterH | r = 64 | 304.4 M | 72.6 | 91.5 |
| LoRA | rv = 2 | 4.7 M | 73.4 | 91.7 |
| LoRA | rq = rv = 1 | 4.7 M | 73.4 | 91.3 |
| LoRA | rq = rv = 2 | 9.4 M | 73.3 | 91.4 |
| LoRA | rq = rk = rv = ro = 1 | 9.4 M | 74.1 | 91.2 |
| LoRA | rq = rv = 4 | 18.8 M | 73.7 | 91.3 |
| LoRA | rq = rk = rv = ro = 2 | 18.8 M | 73.7 | 91.7 |
| LoRA | rq = rv = 8 | 37.7 M | 73.8 | 91.6 |
| LoRA | rq = rk = rv = ro = 4 | 37.7 M | 74.0 | 91.7 |
| LoRA | rq = rv = 64 | 301.9 M | 73.6 | 91.4 |
| LoRA | rq = rk = rv = ro = 64 | 603.8 M | 73.9 | 91.4 |
| LoRA+PE | rq = rv = 8, lp = 8, li = 4 | 37.8 M | 75.0 | 91.4 |
| LoRA+PE | rq = rv = 32, lp = 8, li = 4 | 151.1 M | 75.9 | 91.1 |
| LoRA+PE | rq = rv = 64, lp = 8, li = 4 | 302.1 M | 76.2 | 91.3 |
| LoRA+PL | rq = rv = 8, lp = 8, li = 4 | 52.8 M | 72.9 | 90.2 |

### Table 16：GPT-3 175B 在 MNLI 子集上的验证准确率

| Method | MNLI(m)-100 | MNLI(m)-1k | MNLI(m)-10k | MNLI(m)-392K |
|---|---|---|---|---|
| GPT-3 (Fine-Tune) | 60.2 | 85.8 | 88.9 | 89.5 |
| GPT-3 (PrefixEmbed) | 37.6 | 75.2 | 79.5 | 88.6 |
| GPT-3 (PrefixLayer) | 48.3 | 82.5 | 85.9 | 89.6 |
| GPT-3 (LoRA) | 63.8 | 85.6 | 89.2 | 91.7 |

### Table 17：GPT-3 各适配方法在 MNLI(m)-n 上的超参数

| Hyperparameters | Adaptation | MNLI-100 | MNLI-1k | MNLI-10K | MNLI-392K |
|---|---|---|---|---|---|
| Optimizer | - | AdamW | | | |
| Warmup Tokens | - | 250,000 | | | |
| LR Schedule | - | Linear | | | |
| Batch Size | - | 20 | 20 | 100 | 128 |
| # Epoch | - | 40 | 40 | 4 | 2 |
| Learning Rate | FineTune | 5.00E-6 | | | |
| Learning Rate | PrefixEmbed | 2.00E-04 | 2.00E-04 | 4.00E-04 | 5.00E-04 |
| Learning Rate | PrefixLayer | 5.00E-05 | 5.00E-05 | 5.00E-05 | 1.00E-04 |
| Learning Rate | LoRA | 2.00E-4 | | | |
| Adaptation-Specific | PrefixEmbed lp | 16 | 32 | 64 | 256 |
| Adaptation-Specific | PrefixEmbed li | 8 | | | |
| Adaptation-Specific | PrefixTune | lp = li = 8 | | | |
| Adaptation-Specific | LoRA | rq = rv = 8 | | | |

### Table 18：GPT-2 Medium 在 E2E NLG Challenge 上不同 rank r 的验证损失与测试指标

| Rank r | val loss | BLEU | NIST | METEOR | ROUGE L | CIDEr |
|---|---|---|---|---|---|---|
| 1 | 1.23 | 68.72 | 8.7215 | 0.4565 | 0.7052 | 2.4329 |
| 2 | 1.21 | 69.17 | 8.7413 | 0.4590 | 0.7052 | 2.4639 |
| 4 | 1.18 | 70.38 | 8.8439 | 0.4689 | 0.7186 | 2.5349 |
| 8 | 1.17 | 69.57 | 8.7457 | 0.4636 | 0.7196 | 2.5196 |
| 16 | 1.16 | 69.61 | 8.7483 | 0.4629 | 0.7177 | 2.4985 |
| 32 | 1.16 | 69.33 | 8.7736 | 0.4642 | 0.7105 | 2.5255 |
| 64 | 1.16 | 69.24 | 8.7174 | 0.4651 | 0.7180 | 2.5070 |
| 128 | 1.16 | 68.73 | 8.6718 | 0.4628 | 0.7127 | 2.5030 |
| 256 | 1.16 | 68.92 | 8.6982 | 0.4629 | 0.7128 | 2.5012 |
| 512 | 1.16 | 68.78 | 8.6857 | 0.4637 | 0.7128 | 2.5025 |
| 1024 | 1.17 | 69.37 | 8.7495 | 0.4659 | 0.7149 | 2.5090 |

## 超参数配置（节选）

- Table 9（RoBERTa）：LoRA 配置 `rq = rv = 8`；RoBERTa base `α=8`，RoBERTa large `α=16`；优化器 AdamW，Warmup Ratio 0.06，LR Schedule Linear。
- Table 10（DeBERTa XXL）：LoRA 配置 `rq = rv = 8`，LoRA `α=8`，Warmup Ratio 0.1，LR Schedule Linear，Optimizer AdamW。
- Table 11（GPT-2 LoRA）：Adaptation `rq = rv = 4`，LoRA `α=32`，Batch Size 8，# Epoch 5，Warmup Steps 500，Learning Rate 0.0002，Beam Size 10。

## 理解低秩更新（Section 7）

三组实证研究回答三个问题：(1) 在参数预算约束下应适配哪些权重矩阵；(2) 最优秩 `r` 是多少、`∆W` 是否真的低秩；(3) `∆W` 与 `W` 的关系。

关键结论：

- 在 18M 参数预算下，同时适配 `Wq` 与 `Wv` 效果最佳；仅适配 `Wq` 或 `Wk` 显著较差。
- 即使 `r=4`，`∆W` 也包含足够信息，因此适配更多权重矩阵优于用更大秩适配单一权重。
- `r=1` 即可在 `{Wq, Wv}` 上取得竞争性表现；仅训练 `Wq` 则需要更大 r。
- 增加 `r` 并不会覆盖更有意义的子空间，说明低秩适配矩阵已足够。
- `A_{r=8}` 与 `A_{r=64}` 的顶部奇异向量方向显著重叠（归一化相似度 > 0.5，维度 1），解释了 `r=1` 为何有效。
- `∆Wq` 比 `∆Wv` 具有更高的“内在秩”（两次随机种子运行共享更多奇异值方向）。
- `∆W` 与 `W` 的相关性强于随机矩阵，说明 `∆W` 放大了 `W` 中已有的特征。
- `∆W` 并不重复 `W` 的顶部奇异方向，而是放大 `W` 中未被强调的方向。
- 放大因子很大：`r=4` 时约 21.5（6.91/0.32）。
- LoRA 原则可推广到任何具有稠密层的神经网络。

### 子空间相似度定义（Appendix G）

```
φ(A, B, i, j) = ψ(U_A^i, U_B^j) = ‖U_A^{i⊤} U_B^j‖_F^2 / min{i, j}
```

其中 `U_A^i ∈ R^{d×i}`、`U_B^j ∈ R^{d×j}` 为 A、B 左奇异矩阵取列得到的列正交矩阵。

Projection Metric（Ham & Lee 2008）：

```
d(U_A^i, U_B^j) = sqrt(p − Σ_{i=1}^{p} σ_i^2) ∈ [0, sqrt(p)],  p = min{i, j}
```

两者关系：

```
φ(A, B, i, j) = ψ(U_A^i, U_B^j) = (Σ_{i=1}^{p} σ_i^2) / p = (1/p)(1 − d(U_A^i, U_B^j)^2)
```

性质：若 `U_A^i` 与 `U_B^j` 共享同一列空间，则 `φ = 1`；若完全正交，则 `φ = 0`；否则 `φ ∈ (0, 1)`。

### 放大因子定义（Appendix H.4）

```
amplification factor = ‖ΔW‖_F / ‖U^⊤ W V^⊤‖_F
```

其中 `U`、`V` 为 `ΔW` 的 SVD 左右奇异矩阵；`UU^⊤ W V^⊤V` 给出 `W` 在 `ΔW` 张成子空间上的投影。

## 附录要点

- Appendix A：few-shot learning / prompt engineering 在仅有少量样本时有优势，但性能敏感应用中通常可整理数千条以上训练样本；微调相比 few-shot 大幅提升性能（Table 8）。RTE 的 GPT-3 few-shot 结果取自 Brown et al. (2020)；MNLI-matched 使用每类两个示例、共六个 in-context 示例。
- Appendix B：Adapter 层串行插入，必须与基础模型一起计算，必然引入额外延迟；batch size 与序列长度足够大时可缓解，但在线、短序列场景下延迟可超过 30%。
- Appendix C：数据集细节——WikiSQL（56,355/8,421 训练/验证样本，BSD 3-Clause）、SAMSum（14,732/819，CC BY-NC-ND 4.0）、E2E NLG Challenge（约 42,000/4,600/4,600，CC BY-NC-SA 4.0）、DART（82K，MIT）、WebNLG（22K，14 类，9 类 seen，CC BY-NC-SA 4.0）。
- Appendix E：LoRA+PE 在 WikiSQL 上显著优于 LoRA 与 prefix-embedding tuning，表明 LoRA 与 prefix-embedding tuning 有一定正交性；在 MultiNLI 上 LoRA+PE 未优于 LoRA（LoRA 已接近人类基线）。LoRA+PL 即使参数更多也略差于 LoRA，归因于 prefix-layer tuning 对学习率敏感。
- Appendix F：在 DART 与 WebNLG 上，LoRA 在相同可训练参数下优于或持平 prefix-based 方法。低数据场景（MNLI-100）：PrefixEmbed 仅略优于随机（37.6% vs 33.3%），PrefixLayer 优于 PrefixEmbed 但仍显著差于 Fine-Tune/LoRA；差距随训练样本增加而缩小。LoRA 在 MNLI-100 与 MNLI-Full 上优于微调，在 MNLI-1k/10k 上相当（±0.3 方差）。
- Appendix H：GPT-2 Medium 最优 rank 在 4–16 之间（val loss 峰值 r=16，BLEU 峰值 r=4），与 GPT-3 175B 相似；`ΔW` 顶部 4 个方向与 `W` 顶部 10% 方向的相似度仅略超 0.2；`r=4` 时放大因子高达 20，`r=64` 时仅约 2。

## 局限与未来工作

- 若将 `A`、`B` 合并进 `W` 以消除推理延迟，则难以在单次前向中对不同任务（不同 `A`、`B`）的输入进行批处理；延迟不敏感场景可选择不合并、动态选择 LoRA 模块。
- 适配 MLP 层、LayerNorm 层与 bias 的效果留作未来工作。
- 目前选择应用 LoRA 的权重矩阵主要依赖启发式，缺乏原则化方法。
- `∆W` 的秩亏缺暗示 `W` 本身可能也是秩亏缺的。
- 微调/LoRA 的机制尚不清楚——预训练特征如何转化为下游任务能力；LoRA 使该问题比全量微调更易研究。
- LoRA 可与其他高效适配方法组合，可能带来正交提升。

## 相关工作脉络

- Transformer 语言模型：Vaswani et al. 2017、BERT、GPT-2、GPT-3 175B。
- Prompt Engineering 与 Fine-Tuning。
- Parameter-Efficient Adaptation：adapter 层、[[compacter]]、prefix/embedding 优化、[[bitfit]]、[[prompt-tuning]]、[[adapterfusion]]、[[adapterdrop]]、WARP。
- 深度学习中的低秩结构：低秩张量近似、低秩矩阵分解用于 DNN、因子化神经层初始化与正则化、过参数化矩阵感知中的算法正则化、Jacobian 低秩结构泛化保证、无限宽神经网络中的特征学习。

## 相关页面

- 方法：[[lora]]、[[low-rank-adaptation]]、[[parameter-efficient-adaptation]]、[[adapter-layers]]、[[prefix-tuning]]
- 分析概念：[[intrinsic-rank]]、[[subspace-similarity]]、[[amplification-factor]]
- 模型：[[gpt-3]]、[[gpt-2]]、[[roberta]]、[[deberta]]
- 数据集：[[glue-benchmark]]、[[wikisql]]、[[mnli]]、[[e2e-nlg]]、[[samsum]]、[[webnlg]]、[[dart]]
- 开放问题：[[which-weight-matrices-to-apply-lora]]、[[optimal-lora-rank]]、[[why-do-more-special-tokens-hurt-prefix-tuning]]、[[how-to-principledly-select-weight-matrices-for-lora]]、[[is-w-rank-deficient]]、[[how-does-fine-tuning-transform-pretrained-features]]