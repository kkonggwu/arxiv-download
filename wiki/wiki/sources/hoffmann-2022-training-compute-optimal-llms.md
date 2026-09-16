---
type: source
title: "Training Compute-Optimal Large Language Models (Hoffmann et al., 2022)"
tags: [scaling-laws, compute-optimal, chinchilla, gopher, deepmind, language-models, flops]
related:
  - "[[chinchilla]]"
  - "[[gopher]]"
  - "[[deepmind]]"
  - "[[compute-optimal-training计算最优训练]]"
  - "[[等比例缩放模型规模与训练-token]]"
  - "[[approach-1-固定模型规模变化训练-token]]"
  - "[[approach-2-isoflop-profiles]]"
  - "[[approach-3-参数化损失函数拟合]]"
  - "[[高效计算前沿]]"
  - "[[训练不足-undertrained]]"
  - "[[kaplan-2020-scaling-laws-for-neural-language-models]]"
  - "[[幂律缩放]]"
  - "[[非嵌入参数量]]"
  - "[[gpt-3]]"
  - "[[mt-nlg-530b]]"
  - "[[jurassic-1]]"
  - "[[lamda]]"
  - "[[massivetext]]"
  - "[[the-pile]]"
  - "[[mmlu]]"
  - "[[big-bench]]"
  - "[[winogender]]"
  - "[[perspectiveapi]]"
  - "[[adamw]]"
  - "[[adam]]"
  - "[[sentencepiece]]"
  - "[[tpu]]"
  - "[[jax]]"
  - "[[haiku]]"
  - "[[huber-loss]]"
  - "[[l-bfgs]]"
  - "[[model-card-框架]]"
  - "[[损失分解]]"
  - "[[flop-loss-前沿曲率]]"
  - "[[固定算力下模型规模与数据量应如何权衡]]"
authors: [Jordan Hoffmann, Sebastian Borgeaud, Arthur Mensch, Elena Buchatskaya, Trevor Cai, Eliza Rutherford, Diego de Las Casas, Lisa Anne Hendricks, Johannes Welbl, Aidan Clark, Tom Hennigan, Eric Noland, Katie Millican, George van den Driessche, Bogdan Damoc, Aurelia Guy, Simon Osindero, Karen Simonyan, Erich Elsen, Jack W. Rae, Oriol Vinyals, Laurent Sifre]
year: 2022
url: "https://arxiv.org/abs/2203.15556"
venue: "arXiv preprint (NeurIPS 2022)"
created: 2026-09-16
updated: 2026-09-16
---

# 2022 - Hoffmann et al. - Training Compute-Optimal Large Language Models [2203.15556]

## 概述

本文（Hoffmann et al., 2022, arXiv:2203.15556, DeepMind）研究在固定 FLOPs 计算预算下，transformer 语言模型的最优模型规模（参数量 N）与训练 token 数（D）应如何分配。作者训练了 400 多个语言模型（44M–16B+ 参数，5B–500B token），用三种独立方法估计最优前沿，结论一致：**compute-optimal 训练应使模型规模与训练 token 数近似等比例缩放**（`N_opt ∝ C^a`、`D_opt ∝ C^b`，a≈b≈0.5）。

据此预测，在 Gopher 的算力预算下最优模型应比 Gopher 小约 4 倍、训练 token 多约 4 倍，于是训练了 **Chinchilla**（70B 参数，1.4T token）。Chinchilla 以与 Gopher 相同的 FLOPs 预算，在大量下游任务上一致且显著超越 Gopher (280B)、GPT-3 (175B)、Jurassic-1 (178B)、Megatron-Turing NLG 530B，MMLU 5-shot 平均准确率达 67.6%。

本文结论与 [[kaplan-2020-scaling-laws-for-neural-language-models]]（a=0.73, b=0.27）直接冲突，作者将差异归因于 Kaplan 等人对所有模型使用固定 token 数与固定学习率 schedule，无法建模超参数影响。

## 核心贡献

1. 提出三种估计 compute-optimal 分配的方法（[[approach-1-固定模型规模变化训练-token]]、[[approach-2-isoflop-profiles]]、[[approach-3-参数化损失函数拟合]]），结论一致指向等比例缩放。
2. 指出当前一代大模型相对其算力预算普遍"过大"（over-sized）且"训练不足"（[[训练不足-undertrained]]）。
3. 训练并评测 [[chinchilla]]，验证预测：更小模型 + 更多数据在同算力下全面更优。
4. 在 C4 与 GitHub code 两个额外数据集上复现 IsoFLOP 分析，验证结论不依赖数据集。
5. 给出完整 [[model-card-框架]]、逐任务评测结果与全部训练模型超参数表。

## 三种方法的结果（Table 2）

Table 2 | Estimated parameter and data scaling with increased training compute

| Approach | Coeff. a where N_opt ∝ C^a | Coeff. b where D_opt ∝ C^b |
|---|---|---|
| 1. Minimum over training curves | 0.50 (0.488, 0.502) | 0.50 (0.501, 0.512) |
| 2. IsoFLOP profiles | 0.49 (0.462, 0.534) | 0.51 (0.483, 0.529) |
| 3. Parametric modelling of the loss | 0.46 (0.454, 0.455) | 0.54 (0.542, 0.543) |
| Kaplan et al. (2020) | 0.73 | 0.27 |

## 优化目标（Equation 1）

```
𝑁𝑜𝑝𝑡 (𝐶), 𝐷𝑜𝑝𝑡 (𝐶) = argmin
𝑁,𝐷 s.t. FLOPs(𝑁,𝐷)=𝐶
𝐿(𝑁, 𝐷). (1)
```

## 参数化损失函数与拟合（Equation 2–4）

```
L̂(N, D) = E + A/N^α + B/D^β
```

```
min_{A,B,E,α,β} Σ_Runs i Huber_δ( log L̂(N_i, D_i) − log L_i )
```

```
N_opt(C) = G (C/6)^a,  D_opt(C) = G^{-1} (C/6)^b,
where G = (αA / βB)^{1/(α+β)},  a = β/(α+β),  b = α/(α+β)
```

FLOPs 近似约束：`FLOPs(N, D) ≈ 6ND`（Kaplan et al., 2020）。

## 各模型规模的最优 FLOPs 与 token 数（Table 3，Approach 1 投影）

Table 3 | Estimated optimal training FLOPs and training tokens for various model sizes

| Parameters | FLOPs | FLOPs (in Gopher unit) | Tokens |
|---|---|---|---|
| 400 Million | 1.92e+19 | 1/29,968 | 8.0 Billion |
| 1 Billion | 1.21e+20 | 1/4,761 | 20.2 Billion |
| 10 Billion | 1.23e+22 | 1/46 | 205.1 Billion |
| 67 Billion | 5.76e+23 | 1 | 1.5 Trillion |
| 175 Billion | 3.85e+24 | 6.7 | 3.7 Trillion |
| 280 Billion | 9.90e+24 | 17.2 | 5.9 Trillion |
| 520 Billion | 3.43e+25 | 59.5 | 11.0 Trillion |
| 1 Trillion | 1.27e+26 | 221.3 | 21.2 Trillion |
| 10 Trillion | 1.30e+28 | 22515.9 | 216.2 Trillion |

## 当前大模型规模与训练 token 对比（Table 1）

Table 1 | Current LLMs

| Model | Size (# Parameters) | Training Tokens |
|---|---|---|
| LaMDA (Thoppilan et al., 2022) | 137 Billion | 168 Billion |
| GPT-3 (Brown et al., 2020) | 175 Billion | 300 Billion |
| Jurassic (Lieber et al., 2021) | 178 Billion | 300 Billion |
| Gopher (Rae et al., 2021) | 280 Billion | 300 Billion |
| MT-NLG 530B (Smith et al., 2022) | 530 Billion | 270 Billion |
| Chinchilla | 70 Billion | 1.4 Trillion |

## Chinchilla 与 Gopher 架构对比（Table 4）

Table 4 | Chinchilla architecture details

| Model | Layers | Number Heads | Key/Value Size | d_model | Max LR | Batch Size |
|---|---|---|---|---|---|---|
| Gopher 280B | 80 | 128 | 128 | 16,384 | 4 × 10^-5 | 3M → 6M |
| Chinchilla 70B | 80 | 64 | 128 | 8,192 | 1 × 10^-4 | 1.5M → 3M |

## 评测任务族（Table 5）

Table 5 | All evaluation tasks.

| 类别 | 数量 | 示例 |
|------|------|------|
| Language Modelling | 20 | WikiText-103, The Pile: PG-19, arXiv, FreeLaw, . . . |
| Reading Comprehension | 3 | RACE-m, RACE-h, LAMBADA |
| Question Answering | 3 | Natural Questions, TriviaQA, TruthfulQA |
| Common Sense | 5 | HellaSwag, Winogrande, PIQA, SIQA, BoolQ |
| MMLU | 57 | High School Chemistry, Astronomy, Clinical Knowledge, . . . |
| BIG-bench | 62 | Causal Judgement, Epistemic Reasoning, Temporal Sequences, . . . |

## 主要下游评测结果

### MMLU（Table 6）

Table 6 | Massive Multitask Language Understanding (MMLU).

| 对象 | 准确率 |
|------|--------|
| Random | 25.0% |
| Average human rater | 34.5% |
| GPT-3 5-shot | 43.9% |
| Gopher 5-shot | 60.0% |
| Chinchilla 5-shot | 67.6% |
| Average human expert performance | 89.8% |
| June 2022 Forecast | 57.1% |
| June 2023 Forecast | 63.4% |

Chinchilla 在 51/57 任务上优于 Gopher，2/57 持平，4/57 更差（college_mathematics、econometrics、moral_scenarios、formal_logic）。

### 阅读理解（Table 7）

Table 7 | Reading comprehension.

| 任务 | Chinchilla | Gopher | GPT-3 | MT-NLG 530B |
|------|-----------|--------|-------|-------------|
| LAMBADA Zero-Shot | 77.4 | 74.5 | 76.2 | 76.6 |
| RACE-m Few-Shot | 86.8 | 75.1 | 58.1 | - |
| RACE-h Few-Shot | 82.3 | 71.6 | 46.8 | 47.9 |

### 常识推理（Table 8）

Table 8 | Zero-shot comparison on Common Sense benchmarks.

| 任务 | Chinchilla | Gopher | GPT-3 | MT-NLG 530B | Supervised SOTA |
|------|-----------|--------|-------|-------------|-----------------|
| HellaSWAG | 80.8% | 79.2% | 78.9% | 80.2% | 93.9% |
| PIQA | 81.8% | 81.8% | 81.0% | 82.0% | 90.1% |
| Winogrande | 74.9% | 70.1% | 70.2% | 73.0% | 91.3% |
| SIQA | 51.3% | 50.6% | - | - | 83.2% |
| BoolQ | 83.7% | 79.3% | 60.5% | 78.2% | 91.4% |

### 闭卷问答（Table 9）

Table 9 | Closed-book question answering.

| Method | Chinchilla | Gopher | GPT-3 | SOTA (open book) |
|--------|-----------|--------|-------|------------------|
| Natural Questions (dev) 0-shot | 16.6% | 10.1% | 14.6% | 54.4% |
| Natural Questions (dev) 5-shot | 31.5% | 24.5% | - | 54.4% |
| Natural Questions (dev) 64-shot | 35.5% | 28.2% | 29.9% | 54.4% |
| TriviaQA (unfiltered, test) 0-shot | 67.0% | 52.8% | 64.3% | - |
| TriviaQA (unfiltered, test) 5-shot | 73.2% | 63.6% | - | - |
| TriviaQA (unfiltered, test) 64-shot | 72.3% | 61.3% | 71.2% | - |
| TriviaQA (filtered, dev) 0-shot | 55.4% | 43.5% | - | 72.5% |
| TriviaQA (filtered, dev) 5-shot | 64.1% | 57.0% | - | 72.5% |
| TriviaQA (filtered, dev) 64-shot | 64.6% | 57.2% | - | 72.5% |

### Winogender 偏见与毒性

Winogender 总体：Chinchilla 78.3% vs Gopher 71.4%；Male 71.2% vs 68.0%；Female 79.6% vs 71.3%；Neutral 84.2% vs 75.0%。改进幅度在不同代词间不均衡（female gotcha 提升最大，约 10%）。

毒性（25,000 个无条件样本，PerspectiveAPI）：Gopher 均值 0.081、中位数 0.064、95 分位 0.230；Chinchilla 均值 0.087、中位数 0.066、95 分位 0.238。差异可忽略，说明无条件文本生成的毒性水平大体独立于模型质量（LM loss）。

## 训练数据构成（Table A1）

Table A1 | MassiveText 数据构成

| Subset | Disk Size | Documents | Sampling proportion | Epochs in 1.4T tokens |
|---|---|---|---|---|
| MassiveWeb | 1.9 TB | 604M | 45% (48%) | 1.24 |
| Books | 2.1 TB | 4M | 30% (27%) | 0.75 |
| C4 | 0.75 TB | 361M | 10% (10%) | 0.77 |
| News | 2.7 TB | 1.1B | 10% (10%) | 0.21 |
| GitHub | 3.1 TB | 142M | 4% (3%) | 0.13 |
| Wikipedia | 0.001 TB | 6M | 1% (2%) | 3.40 |

## 跨数据集缩放一致性（Table A2）

Table A2 | 缩放系数

| Approach | a (N_opt ∝ C^a) | b (D_opt ∝ C^b) |
|---|---|---|
| C4 | 0.50 | 0.50 |
| GitHub | 0.53 | 0.47 |
| Kaplan et al. (2020) | 0.73 | 0.27 |

## 损失分解（Equation 5–8）

```
L̂(N, D) ≜ E + A/N^α + B/D^β
```

```
L(f) ≜ E[log f(x)_y],  f* ≜ argmin_{f ∈ F(X, D(Y))} L(f)
f_N ≜ argmin_{f ∈ H_N} L(f)
L̂_D(f) ≜ Ê_D[log f(x)_y],  f̂_{N,D} ≜ argmin_{f ∈ H_N} L̂_D(f)
L(N, D) ≜ L(f̄_{N,D}) = L(f*) + [L(f_N) − L(f*)] + ...
```

损失分解为三项：Bayes risk（自然文本熵）、functional approximation term（依赖 N，两层网络下预期 ∝ 1/N^{1/2}）、stochastic approximation term（依赖 D，收敛率下界 1/D^{1/2}）。

## 损失分解拟合结果（Equation 10–11）

```
L(N, D) = E + A/N^0.34 + B/D^0.28
E = 1.69, A = 406.4, B = 410.7
```

```
min_{a,b,e,α,β} Σ_Run i Huber_δ( LSE(a − α log N_i, b − β log D_i, e) − log L_i )
```

初始化网格：α ∈ {0., 0.5, …, 2.}，β ∈ {0., 0.5, …, 2.}，e ∈ {−1., −.5, …, 1.}，a ∈ {0, 5, …, 25}，b ∈ {0, 5, …, 25}；Huber δ = 10⁻³。

## Approach 2 与 Approach 3 的前沿预测（Table A3）

Table A3 | Approach 2 与 Approach 3 的估计最优训练 FLOPs 与 token 数

| Parameters | Approach 2 FLOPs | Approach 2 Tokens | Approach 3 FLOPs | Approach 3 Tokens |
|---|---|---|---|---|
| 400 Million | 1.84e+19 | 7.7 Billion | 2.21e+19 | 9.2 Billion |
| 1 Billion | 1.20e+20 | 20.0 Billion | 1.62e+20 | 27.1 Billion |
| 10 Billion | 1.32e+22 | 219.5 Billion | 2.46e+22 | 410.1 Billion |
| 67 Billion | 6.88e+23 | 1.7 Trillion | 1.71e+24 | 4.1 Trillion |
| 175 Billion | 4.54e+24 | 4.3 Trillion | 1.26e+24 | 12.0 Trillion |
| 280 Billion | 1.18e+25 | 7.1 Trillion | 3.52e+25 | 20.1 Trillion |
| 520 Billion | 4.19e+25 | 13.4 Trillion | 1.36e+26 | 43.5 Trillion |
| 1 Trillion | 1.59e+26 | 26.5 Trillion | 5.65e+26 | 94.1 Trillion |
| 10 Trillion | 1.75e+28 | 292.0 Trillion | 8.55e+28 | 1425.5 Trillion |

## FLOP 比值（Table A4）

Table A4 | FLOP 比值（Ours / 6ND）

| Parameters | num_layers | d_model | ffw_size | num_heads | k/q size | FLOP Ratio |
|---|---|---|---|---|---|---|
| 73M | 10 | 640 | 2560 | 10 | 64 | 1.03 |
| 305M | 20 | 1024 | 4096 | 16 | 64 | 1.10 |
| 552M | 24 | 1280 | 5120 | 10 | 128 | 1.08 |
| 1.1B | 26 | 1792 | 7168 | 14 | 128 | 1.04 |
| 1.6B | 28 | 2048 | 8192 | 16 | 128 | 1.03 |
| 6.8B | 40 | 3584 | 14336 | 28 | 128 | 0.99 |

## The Pile bits-per-byte（Table A5）

Table A5 | The Pile bits-per-byte（Chinchilla 70B / Gopher 280B / Jurassic-1 170B）

| Subset | Chinchilla | Gopher | Jurassic-1 |
|---|---|---|---|
| pile_cc | 0.667 | 0.691 | 0.669 |
| pubmed_abstracts | 0.559 | 0.578 | 0.587 |
| stackexchange | 0.614 | 0.641 | 0.655 |
| github | 0.337 | 0.377 | 0.358 |
| openwebtext2 | 0.647 | 0.677 | - |
| arxiv | 0.627 | 0.662 | 0.680 |
| uspto_backgrounds | 0.526 | 0.546 | 0.537 |
| freelaw | 0.476 | 0.513 | 0.514 |
| pubmed_central | 0.504 | 0.525 | 0.579 |
| dm_mathematics | 1.111 | 1.142 | 1.037 |
| hackernews | 0.859 | 0.890 | 0.869 |
| nih_exporter | 0.572 | 0.590 | 0.590 |
| opensubtitles | 0.871 | 0.900 | 0.879 |
| europarl | 0.833 | 0.938 | - |
| books3 | 0.675 | 0.712 | 0.835 |
| philpapers | 0.656 | 0.695 | 0.742 |
| gutenberg_pg_19 | 0.548 | 0.656 | 0.890 |
| bookcorpus2 | 0.714 | 0.741 | - |
| ubuntu_irc | 1.026 | 1.090 | 0.857 |

## FLOPs 计算方法（Appendix F）

```
Forward pass:
- Embeddings: 2 × seq_len × vocab_size × d_model
- Attention (Single Layer):
  - Key, query and value projections: 2 × 3 × seq_len × d_model × (key_size × num_heads)
  - Key @ Query logits: 2 × seq_len × seq_len × (key_size × num_heads)
  - Softmax: 3 × num_heads × seq_len × seq_len
  - Softmax @ query reductions: 2 × seq_len × seq_len × (key_size × num_heads)
  - Final Linear: 2 × seq_len × (key_size × num_heads) × d_model
- Dense Block (Single Layer): 2 × seq_len × (d_model × ffw_size + d_model × ffw_size)
- Final Logits: 2 × seq_len × d_model × vocab_size
- Total forward pass FLOPs: embeddings + num_layers × (total_attention + dense_block) + logits
Backward pass = 2 × forward pass
```

## 全部训练模型超参数（Table A9）

Table A9 | All models（超参数与规模）

| Parameters (million) | d_model | ffw_size | kv_size | n_heads | n_layers |
|---|---|---|---|---|---|
| 44 | 512 | 2048 | 64 | 8 | 8 |
| 57 | 576 | 2304 | 64 | 9 | 9 |
| 74 | 640 | 2560 | 64 | 10 | 10 |
| 90 | 640 | 2560 | 64 | 10 | 13 |
| 106 | 640 | 2560 | 64 | 10 | 16 |
| 117 | 768 | 3072 | 64 | 12 | 12 |
| 140 | 768 | 3072 | 64 | 12 | 15 |
| 163 | 768 | 3072 | 64 | 12 | 18 |
| 175 | 896 | 3584 | 64 | 14 | 14 |
| 196 | 896 | 3584 | 64 | 14 | 16 |
| 217 | 896 | 3584 | 64 | 14 | 18 |
| 251 | 1024 | 4096 | 64 | 16 | 16 |
| 278 | 1024 | 4096 | 64 | 16 | 18 |
| 306 | 1024 | 4096 | 64 | 16 | 20 |
| 425 | 1280 | 5120 | 128 | 10 | 18 |
| 489 | 1280 | 5120 | 128 | 10 | 21 |
| 509 | 1408 | 5632 | 128 | 11 | 18 |
| 552 | 1280 | 5120 | 128 | 10 | 24 |
| 587 | 1408 | 5632 | 128 | 11 | 21 |
| 632 | 1536 | 6144 | 128 | 12 | 19 |
| 664 | 1408 | 5632 | 128 | 11 | 24 |
| 724 | 1536 | 6144 | 128 | 12 | 22 |
| 816 | 1536 | 6144 | 128 | 12 | 25 |
| 893 | 1792 | 7168 | 128 | 14 | 20 |
| 1,018 | 1792 | 7168 | 128 | 14 | 23 |
| 1,143 | 1792 | 7168 | 128 | 14 | 26 |
| 1,266 | 2048 | 8192 | 128 | 16 | 22 |
| 1,424 | 2176 | 8704 | 128 | 17 | 22 |
| 1,429 | 2048 | 8192 | 128 | 16 | 25 |
| 1,593 | 2048 | 8192 | 128 | 16 | 28 |
| 1,609 | 2176 | 8704 | 128 | 17 | 25 |
| 1,731 | 2304 | 9216 | 128 | 18 | 24 |
| 1,794 | 2176 | 8704 | 128 | 17 | 28 |
| 2,007 | 2304 | 9216 | 128 | 18 | 28 |
| 2,283 | 2304 | 9216 | 128 | 18 | 32 |
| 2,298 | 2560 | 10240 | 128 | 20 | 26 |
| 2,639 | 2560 | 10240 | 128 | 20 | 30 |
| 2,980 | 2560 | 10240 | 128 | 20 | 34 |
| 3,530 | 2688 | 10752 | 128 | 22 | 36 |
| 3,802 | 2816 | 11264 | 128 | 22 | 36 |
| 4,084 | 2944 | 11776 | 128 | 22 | 36 |
| 4,516 | 3072 | 12288 | 128 | 24 | 36 |
| 6,796 | 3584 | 14336 | 128 | 28 | 40 |
| 9,293 | 4096 | 16384 | 128 | 32 | 42 |
| 11,452 | 4352 | 17408 | 128 | 32 | 47 |
| 12,295 | 4608 | 18432 | 128 | 36 | 44 |
| 12,569 | 4608 | 18432 | 128 | 32 | 47 |
| 13,735 | 4864 | 19456 | 128 | 32 | 47 |
| 14,940 | 4992 | 19968 | 128 | 32 | 49 |
| 16,183 | 5120 | 20480 | 128 | 40 | 47 |

## 主要主张与发现

- 三种方法一致表明：随算力增加，模型规模与训练 token 数应近似等比例增长（a≈b≈0.5）。
- 当前大模型相对其算力预算普遍过大（over-sized）且训练不足。
- 175B 模型应配约 4.41×10^24 FLOPs 与 4.2T+ token；280B 模型对应约 10^25 FLOPs 与 6.8T token；1T 参数模型需约 10^26 FLOPs（Gopher 算力的 250×+）才可能最优。
- Chinchilla 与 Gopher 同 FLOPs，但更小、数据更多，内存与推理成本约为 1/4。
- 在 10²¹ FLOPs 上，Approach 1 预测最优 2.86B 参数，Kaplan et al. (2020) 预测 4.68B；实测 2.80B 模型优于 4.74B 模型。
- AdamW 训练模型在任意学习率 schedule 下均优于 Adam；Chinchilla 使用 AdamW 并在 sharded optimiser state 中存储更高精度权重副本。
- FLOP-loss 前沿存在曲率，暗示更大 FLOP 预算下可能更小模型才最优（留作未来工作）。
- 无条件文本生成的毒性水平大体独立于模型质量（LM loss）。

## 局限与开放问题

- 大规模仅两次可比运行（Chinchilla、Gopher），无中间规模额外测试。
- 假设高效计算前沿为幂律；log N_opt 在高算力下呈凹性，可能仍高估大模型最优规模。
- 所有分析训练均不足一个 epoch；多 epoch 训练机制留作未来工作。
- 拟合得到 α=0.34、β=0.28，均低于 1/2 的理论下界，如何提高这些系数尚不明确。
- 未研究交叉性（intersectional）偏差。
- 数据集质量如何量化及其对缩放收益的影响未解决。
- 偏见改进不均衡（不同代词/性别子群）的机制未解释。

## 相关页面

- 模型：[[chinchilla]]、[[gopher]]、[[gpt-3]]、[[jurassic-1]]、[[mt-nlg-530b]]、[[lamda]]
- 机构：[[deepmind]]
- 概念：[[compute-optimal-training计算最优训练]]、[[等比例缩放模型规模与训练-token]]、[[训练不足-undertrained]]、[[高效计算前沿]]、[[flop-loss-前沿曲率]]、[[损失分解]]、[[幂律缩放]]、[[非嵌入参数量]]
- 方法：[[approach-1-固定模型规模变化训练-token]]、[[approach-2-isoflop-profiles]]、[[approach-3-参数化损失函数拟合]]
- 数据集与基准：[[massivetext]]、[[the-pile]]、[[mmlu]]、[[big-bench]]、[[winogender]]、[[perspectiveapi]]
- 工具：[[adamw]]、[[adam]]、[[sentencepiece]]、[[tpu]]、[[jax]]、[[haiku]]、[[huber-loss]]、[[l-bfgs]]
- 对照：[[kaplan-2020-scaling-laws-for-neural-language-models]]
- 开放问题：[[固定算力下模型规模与数据量应如何权衡]]
