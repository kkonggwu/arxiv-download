---
type: entity
title: Chinchilla
tags: [model, language-model, compute-optimal, deepmind]
related:
  - "[[gopher]]"
  - "[[gpt-3]]"
  - "[[jurassic-1]]"
  - "[[megatron-turing-nlg-530b]]"
  - "[[lamda]]"
  - "[[deepmind]]"
  - "[[massive-text]]"
  - "[[compute-optimal-training]]"
  - "[[isoflop-profiles]]"
  - "[[parametric-loss-fitting]]"
  - "[[kaplan-2020-scaling-laws-for-neural-language-models]]"
  - "[[hoffmann-2022-training-compute-optimal-llms]]"
created: 2026-09-16
updated: 2026-09-16
---

# Chinchilla

## 概述

Chinchilla 是 DeepMind 于 2022 年在论文《Training Compute-Optimal Large Language Models》（Hoffmann et al., 2022, arXiv:2203.15556）中提出的 70B 参数语言模型，训练 token 数达 1.4T。它是该论文核心结论的直接产物：在固定 FLOPs 预算下，模型规模与训练 token 数应当**等比例**缩放（模型规模翻倍，训练 token 数也应翻倍），而非像此前实践那样只扩大模型规模而保持训练数据量不变。

Chinchilla 使用与 [[gopher]] 相同的算力预算（FLOPs），但模型规模更小（70B vs 280B）、训练数据更多（1.4T vs 300B token），在大量下游任务上一致且显著超越 Gopher、[[gpt-3]]、[[jurassic-1]] 与 [[megatron-turing-nlg-530b]]。其内存与推理成本约为 Gopher 的 1/4。

## 架构与训练细节

| 项目 | Chinchilla | Gopher（对照） |
|---|---|---|
| 参数量 | 70B | 280B |
| 训练 token 数 | 1.4T | 300B |
| 层数 | 80 | 80 |
| Attention heads | 64 | 128 |
| d_model | 8192 | 16384 |
| Max LR | 1e-4 | 4e-5 |
| 优化器 | AdamW + 高精度权重副本 | Adam |

- **数据集**：使用 [[massive-text]]（与 Gopher 同数据集，子集分布略调，见论文 Table A1）。
- **优化器**：用 AdamW 替代 Adam。论文指出 AdamW 相比 Adam 改善语言建模 loss 与微调后下游性能（AdamW 约在 cosine cycle 80% 处才追平 Adam 训练性能，但最终性能更好）。
- **Tokenizer**：SentencePiece，词表 32,000，不做 NFKC normalization（94.15% token 与 Gopher 相同，利于数学与化学表示）。
- **精度**：前向/反向用 bfloat16，分布式优化器状态保留 float32 权重副本。
- **硬件与框架**：训练于 TPUv3/TPUv4，使用 JAX 与 Haiku。

## 性能表现

Chinchilla 在广泛下游评测上全面超越同期更大模型：

- **MMLU**：平均准确率 67.6%（论文摘要与正文中亦出现 67.5% 的表述），比 Gopher 提升 7%+。
- 在 BIG-bench、LAMBADA、RACE、Natural Questions、TriviaQA、TruthfulQA、HellaSwag、PIQA、SIQA、Winogrande、BoolQ、SocialIQA 等任务上一致优于 Gopher、GPT-3、Jurassic-1、MT-NLG 530B。
- 论文第 4.2 节给出广泛下游评测；文末（第 33–36 页）给出完整 Chinchilla Model Card（含评测数据集、预处理、伦理考量）、BIG-bench 逐任务结果（Table A7）与全部训练模型超参数表（Table A9）。

## 与同期模型的对比

论文 Table 1 列出当时主流大模型：

| Model | Size (# Parameters) | Training Tokens |
|---|---|---|
| LaMDA (Thoppilan et al., 2022) | 137 Billion | 168 Billion |
| GPT-3 (Brown et al., 2020) | 175 Billion | 300 Billion |
| Jurassic (Lieber et al., 2021) | 178 Billion | 300 Billion |
| Gopher (Rae et al., 2021) | 280 Billion | 300 Billion |
| MT-NLG 530B (Smith et al., 2022) | 530 Billion | 270 Billion |
| Chinchilla | 70 Billion | 1.4 Trillion |

Chinchilla 以最小的参数量、最多的训练 token 数，取得最优性能，直接印证了"当前大模型普遍训练不足（undertrained）"的判断。

## 理论依据

Chinchilla 的规模与数据配比来自论文第 3 节的三种方法（[[compute-optimal-training]]）：

- **Approach 1**（固定模型规模、变化训练 token 数）：得 a=0.50、b=0.50。
- **Approach 2**（[[isoflop-profiles]]）：得 a=0.49、b=0.51。
- **Approach 3**（[[parametric-loss-fitting]]）：提出 `L̂(N,D) = E + A/N^α + B/D^β`，用 Huber loss（δ=10^-3）与 L-BFGS 拟合，得 a=0.46、b=0.54。

三种方法一致指向参数与训练 token 应近似等比例增长。据此，Gopher 算力预算下的最优规模在 40–70B 之间，故选择 70B、1.4T token 训练 Chinchilla。

## 与 Kaplan 缩放律的冲突

Chinchilla 的结论与 [[kaplan-2020-scaling-laws-for-neural-language-models]]（Kaplan et al., 2020，a=0.73, b=0.27）直接冲突。论文解释差异来源：

1. Kaplan 对所有模型用固定 token 数与固定学习率 schedule，无法建模超参影响；本文发现学习率 schedule 长度应大致匹配训练 token 数。
2. 本文纳入最大 16B 参数模型，观察到 FLOP-loss 前沿存在轻微曲率，且多数模型 >500M 参数，而 Kaplan 多数 <100M。

Kaplan 固定 token 数与 schedule 导致中间 loss 高估，从而低估小数据训练效果，最终得出"模型应比数据增长更快"的结论。

## 开放问题

- 大模型规模下 FLOP-loss 前沿曲率是否需纳入建模（作者留作 future work）。
- 更大、更高质量数据集在进一步缩放中的关键作用（作者指出但未解决）。
- 1T 参数模型需约 10^26 FLOPs（Gopher 算力的 250×+）才可能最优，所需训练数据量远超当前实践。

## 相关页面

- [[gopher]] — 同算力预算的对照模型（280B，300B token）
- [[gpt-3]] — 175B，300B token
- [[jurassic-1]] — 178B，300B token（AI21 Labs）
- [[megatron-turing-nlg-530b]] — 530B，270B token
- [[lamda]] — 137B，168B token
- [[deepmind]] — 提出机构
- [[massive-text]] — 训练数据集
- [[compute-optimal-training]] — 核心概念
- [[isoflop-profiles]] — Approach 2
- [[parametric-loss-fitting]] — Approach 3
- [[kaplan-2020-scaling-laws-for-neural-language-models]] — 冲突来源
- [[hoffmann-2022-training-compute-optimal-llms]] — 来源论文