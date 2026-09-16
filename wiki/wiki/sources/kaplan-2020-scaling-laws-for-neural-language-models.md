---
type: source
title: "Scaling Laws for Neural Language Models (Kaplan et al., 2020)"
tags: [scaling-laws, language-model, transformer, power-law, compute-optimal, openai]
related:
  - "[[openai]]"
  - "[[gpt-3]]"
  - "[[transformer]]"
  - "[[scaling-laws-for-neural-language-models神经语言模型缩放定律]]"
  - "[[幂律缩放]]"
  - "[[临界batch-size]]"
  - "[[计算高效前沿]]"
  - "[[非嵌入参数量]]"
  - "[[webtext2]]"
  - "[[adam]]"
  - "[[adafactor]]"
  - "[[缩放定律失效点]]"
  - "[[上下文位置幂律]]"
  - "[[学习率调度无关性]]"
  - "[[泛化对深度的独立性]]"
authors: [Jared Kaplan, Sam McCandlish, Tom Henighan, Tom B. Brown, Benjamin Chess, Rewon Child, Scott Gray, Alec Radford, Jeffrey Wu, Dario Amodei]
year: 2020
url: "https://arxiv.org/abs/2001.08361"
venue: "arXiv preprint (arXiv:2001.08361v1)"
created: 2026-09-16
updated: 2026-09-16
---

# 2020 - Kaplan et al. - Scaling Laws for Neural Language Models [2001.08361]

## 概述

本文（Kaplan et al., 2020, arXiv:2001.08361v1）研究 Transformer 语言模型的交叉熵损失如何随规模变化，发现损失对**非嵌入参数量 N**、**数据集规模 D**、**训练计算量 C** 呈精确的幂律下降，趋势跨越七个数量级以上。核心结论是：性能强烈依赖规模，而弱依赖网络形状（深度、宽度、注意力头数、前馈维度）。作者据此给出过拟合的联合方程、学习曲线方程、临界 batch size 幂律，以及固定计算预算下的最优分配策略。

作者为 Jared Kaplan（Johns Hopkins University / OpenAI）、Sam McCandlish（OpenAI）等共 10 人，全部隶属或合作于 [[openai]]。本文是 [[gpt-3]] 等后续大模型训练策略的理论基础之一，也是 [[scaling-laws-for-neural-language-models神经语言模型缩放定律]] 这一研究方向的奠基性工作。

## 核心主张

- 性能强依赖规模，弱依赖模型形状；固定 N 时 aspect ratio 可变化 40× 而性能仅微降。
- 三条基本幂律指数：αN ≈ 0.076、αD ≈ 0.095、αC^min ≈ 0.050。
- 大模型样本效率更高；固定计算预算下最优策略是训练超大模型并显著提前停止（远未收敛）。
- 数据需求随计算增长缓慢：D ∝ C^0.27。
- 临界 batch size 仅依赖损失 L，不直接依赖模型规模；损失每降 13%，Bcrit 约翻倍。
- 数值常数 Nc、Dc、Cc^min 依赖词表与分词，无根本意义。
- 在远超实验规模处，L(Cmin) 与 L(D) 两条幂律相交，构成内在矛盾，作者推测该交点标志最大性能点。

## 关键公式（逐字保留）

```
L(N) = (Nc/N)^αN ; αN ∼ 0.076, Nc ∼ 8.8 × 10^13 (non-embedding parameters)   (1.1)

L(D) = (Dc/D)^αD ; αD ∼ 0.095, Dc ∼ 5.4 × 10^13 (tokens)                       (1.2)

L(Cmin) = (Cc^min/Cmin)^αC^min ; αC^min ∼ 0.050, Cc^min ∼ 3.1 × 10^8 (PF-days)  (1.3)

Bcrit(L) = B∗ / L^(1/αB), B∗ ∼ 2 · 10^8 tokens, αB ∼ 0.21                       (1.4)

L(N, D) = [ (Nc/N)^(αN/αD) + Dc/D ]^αD                                          (1.5)

L(N, S) = (Nc/N)^αN + (Sc/Smin(S))^αS,  Sc ≈ 2.1 × 10^3, αS ≈ 0.76            (1.6)

N ∝ C^(αC^min/αN), B ∝ C^(αC^min/αB), S ∝ C^(αC^min/αS), D = B · S            (1.7)

αC^min = 1 / (1/αS + 1/αB + 1/αN)                                              (1.8)
```

Transformer 参数与计算量：

```
N ≈ 2 dmodel nlayer (2 dattn + dff)
  = 12 nlayer dmodel^2   with the standard dattn = dff/4 = dmodel              (2.1)

Cforward ≈ 2N + 2 nlayer nctx dmodel                                          (2.2)

C ≈ 6NBS   (total non-embedding training compute)
1 PF-day = 10^15 × 24 × 3600 = 8.64 × 10^19 floating point operations
```

## 符号表

| 符号 | 含义 |
|------|------|
| L | 交叉熵损失（nats） |
| N | 模型参数量（不含词表与位置嵌入） |
| C | 总非嵌入训练计算量 ≈ 6NBS |
| D | 数据集规模（tokens） |
| Bcrit | 临界 batch size |
| Cmin | 达到给定损失的最小非嵌入计算量估计 |
| Smin | 达到给定损失的最小训练步数估计 |
| αX | 损失缩放幂律指数，L(X) ∝ 1/X^αX |

## Table 1：Transformer 参数与计算量逐操作估算

| Operation | Parameters | FLOPs per Token |
|---|---|---|
| Embed | (n_vocab + n_ctx) d_model | 4 d_model |
| Attention: QKV | n_layer d_model 3 d_attn | 2 n_layer d_model 3 d_attn |
| Attention: Mask | — | 2 n_layer n_ctx d_attn |
| Attention: Project | n_layer d_attn d_model | 2 n_layer d_attn d_embd |
| Feedforward | n_layer 2 d_model d_ff | 2 n_layer 2 d_model d_ff |
| De-embed | — | 2 d_model n_vocab |
| Total (Non-Embedding) | N = 2 d_model n_layer (2 d_attn + d_ff) | C_forward = 2N + 2 n_layer n_ctx d_attn |

## Table 2：L(N, D) 拟合参数

| Parameter | αN | αD | Nc | Dc |
|---|---|---|---|---|
| Value | 0.076 | 0.103 | 6.4 × 10^13 | 1.8 × 10^13 |

## Table 3：L(N, S) 拟合参数

| Parameter | αN | αS | Nc | Sc |
|---|---|---|---|---|
| Value | 0.077 | 0.76 | 6.5 × 10^13 | 2.1 × 10^3 |

## Table 4：附录 A 幂律趋势汇总

| Parameters | Data | Compute | Batch Size | Equation |
|---|---|---|---|---|
| N | ∞ | ∞ | Fixed | L(N) = (Nc/N)^αN |
| ∞ | D | Early Stop | Fixed | L(D) = (Dc/D)^αD |
| Optimal | ∞ | C | Fixed | L(C) = (Cc/C)^αC (naive) |
| Nopt | Dopt | Cmin | B ≪ Bcrit | L(Cmin) = (Cc^min/Cmin)^αC^min |
| N | D | Early Stop | Fixed | L(N, D) = [(Nc/N)^(αN/αD) + Dc/D]^αD |
| N | ∞ | S steps | B | L(N, S) = (Nc/N)^αN + (Sc/Smin(S,B))^αS |

## Table 5：经验拟合值（tokenization-dependent）

| Power Law | Scale (tokenization-dependent) |
|---|---|
| αN = 0.076 | Nc = 8.8 × 10^13 params (non-embed) |
| αD = 0.095 | Dc = 5.4 × 10^13 tokens |
| αC = 0.057 | Cc = 1.6 × 10^7 PF-days |
| αC^min = 0.050 | Cc^min = 3.1 × 10^8 PF-days |
| αB = 0.21 | B* = 2.1 × 10^8 tokens |
| αS = 0.76 | Sc = 2.1 × 10^3 steps |

## Table 6：计算高效最优参数

| Compute-Efficient Value | Power Law | Scale |
|---|---|---|
| Nopt = Ne · Cmin^pN | pN = 0.73 | Ne = 1.3 · 10^9 params |
| B ≪ Bcrit = B*/L^(1/αB) = Be·Cmin^pB | pB = 0.24 | Be = 2.0 · 10^6 tokens |
| Smin = Se · Cmin^pS (lower bound) | pS = 0.03 | Se = 5.4 · 10^3 steps |
| Dopt = De · Cmin^pD (1 epoch) | pD = 0.27 | De = 2 · 10^10 tokens |

## 第 4–6 节关键公式（逐字保留）

```
δL(N, D) ≡ L(N, D)/L(N, ∞) − 1            (4.2)

δL ≈ [ (1 + (N/Nc)^(αN/αD) · (Dc/D))^αD ] − 1   (4.3)

D ≳ (5 × 10^3) N^0.74                       (4.4)

(S/Smin − 1)(E/Emin − 1) = 1                (5.1)

Bcrit(L) ≡ Emin/Smin                        (5.2)

Bcrit(L) ≈ B*/L^(1/αB),  B* ≈ 2×10^8, αB ≈ 0.21   (5.3)

Smin(S) ≡ S / (1 + Bcrit(L)/B)              (5.4)

Cmin(C) ≡ C / (1 + B/Bcrit(L)),  C = 6NBS    (5.5)

L(N, Smin) = (Nc/N)^αN + (Sc/Smin)^αS       (5.6)

Sstop(N, D) ≳ Sc / [L(N, D) − L(N, ∞)]^(1/αS)   (5.7)

N(Cmin) ∝ (Cmin)^0.73                        (6.1)

Smin ∝ (Cmin)^0.03                           (6.2)

L(Cmin) = (Cc^min / Cmin)^αC^min             (6.3)

αC^min ≡ 1 / (1/αS + 1/αB + 1/αN) ≈ 0.054    (6.4)

N(Cmin) ∝ (Cmin)^(αC^min/αN) ≈ (Cmin)^0.71   (6.5)
```

## 附录 B 关键方程（逐字保留）

```
L(N, S) = (Nc/N)^αN + (Sc/S)^αS                                    (B.1)
B(L) = B* / L^(1/αB)                                               (B.2)
L(N, C) = (Nc/N)^αN + (6B*Sc / (N L^(1/αB) C))^αS                  (B.3)
αN/αS · (Nc/N)^αN = (6B*Sc / (N L^(1/αB) C))^αS                    (B.4)
L(Neff(C), C) = (1 + αN/αS) L(Neff, ∞)                             (B.5)
L(C) = (Cc/C)^αC                                                   (B.6)
αC = 1/(1/αS + 1/αB + 1/αN) ≈ 0.052                                (B.7)
Cc = 6NcB*Sc (1 + αN/αS)^(1/αS + 1/αN) (αS/αN)^(1/αS)             (B.8)
N(C)/Nc = (C/Cc)^(αC/αN) (1 + αN/αS)^(1/αN)                        (B.9)
S(C) = Cc/(6NcB*) (1 + αN/αS)^(-1/αN) (C/Cc)^(αC/αS)               (B.10)
L(N, C) = (1 + f) L(N, ∞)                                          (B.11)
Nf/Nf' = ((1+f)/(1+f'))^(1/αN) ≈ 2.7                               (B.12)
```

## 附录 B.3–B.4 与附录 D 关键公式（逐字保留）

```
Nf/Nf0 = ((1+f)/(1+f0))^(1/αN) ≈ 2.7          (B.12)
Sf/Sf0 = ((1+1/f)/(1+1/f0))^(1/αS) ≈ 0.13     (B.13)
Cf/Cf0 = (Nf/Nf0)(Sf/Sf0) ≈ 0.35              (B.14)

C(N, L) = (6B*Sc/N · L^(1/αB)) · (L − (Nc/N)^αN)^(−1/αS)   (B.15)

C(N, Neff)/C(Neff, Neff) = N/Neff · [1 + (αS/αN)(1 − (Neff/N)^αN)]^(−1/αS)   (B.16)

S(N, Neff)/S(Neff, Neff) = [1 + (αS/αN)(1 − (Neff/N)^αN)]^(−1/αS)   (B.17)

LR(N) ≈ 0.003239 + (−0.0001395) log(N)        (D.1)
```

## 训练设置与数据集

- 优化器：[[adam]]；参数量 > 1B 时使用 [[adafactor]]。
- 训练步数 2.5×10^5，batch 512×1024，3000 步线性 warmup + cosine 衰减。
- 主数据集 [[webtext2]]：Reddit 外链（2017-12 前 + 2018-01 至 2018-10，≥3 karma），Newspaper3k 提取，20.3M 文档、96 GB、1.62×10^10 词、2.29×10^10 tokens、6.6×10^8 测试 tokens，BPE 词表 50257；1.4 tokens/word，4.3 characters/token。
- 额外测试分布：Books Corpus、Common Crawl、English Wikipedia、Internet Books。
- 对比模型：LSTM、Universal Transformers / recurrent Transformers [DGV+18]。

## 主要发现

- 固定 N 时性能对形状（深度/宽度/头数/前馈维度）依赖极弱；(6,4288) 与 (48,1600) 损失相差 3% 以内；22% 额外计算可补偿 1% 损失增加。
- LSTM 在上下文早期 token 与 Transformer 相当，但无法匹配后期 token；Transformer 因更好利用长上下文而渐近超越。
- 泛化几乎只依赖 in-distribution 验证损失，不依赖训练时长、收敛程度或模型深度。
- 样本效率随模型增大而提升；达到固定损失的最小步数随模型规模急剧下降，样本效率提升近 100×（图 19）。
- 随机种子导致的损失波动约 0.02；避免过拟合需 D ≳ (5×10^3) N^0.74。
- <10^9 参数模型可在 22B token WebText2 上几乎无过拟合；最大模型出现轻微过拟合。
- 最优分配：N ∝ C^0.73（经验）/ C^0.71（理论），S ∝ C^0.03（可能为 0），Bcrit ∝ C^0.24。
- 0.6×–2.2× 最优规模模型可用多 20% 计算预算训练；2.2× 更大模型需 45% 更少步数但多 20% 训练计算。
- 计算高效训练使用 7.7× 更少参数更新、2.7× 更多参数、65% 更少计算达到相同损失。
- 损失随上下文位置 T 呈幂律（拟合式 4.0 + 3.2 T^−0.47 至 2.3 + 5.4 T^−0.62）；模型先学短程信息，后学长程相关性。
- 学习率调度选择基本无关，run-to-run 波动约 0.05；LR(N) 经验公式在 N > 10^10 时失效。
- 幂律拟合定性优于对数拟合。
- 泛化到其他分布不依赖深度，仅依赖训练分布性能。

## 内在矛盾与注意事项

- **内在矛盾**：在远超实验规模处，L(Cmin) 与 L(D) 两条幂律相交（图 15）。交点 C* ~ 10^4 PF-Days, N* ~ 10^12 参数, D* ~ 10^12 tokens, L* ~ 1.7 nats/token（高度不确定，可浮动一个数量级）。作者推测该交点可能标志 Transformer 语言模型能达到的最大性能，并给出 L* 作为自然语言每 token 熵的粗略估计。
- 为避免过拟合需 D ∝ Cmin^0.54；计算高效训练数据仅 ∝ Cmin^0.26，两者增长速率不匹配，暗示计算高效训练最终会撞上过拟合瓶颈。
- 附录 C 六条 caveat：(1) 缩放定律缺乏坚实理论理解，尤其模型规模与计算量的缩放关系；(2) 对远超实验范围的 Bcrit(L) 预测不自信；(3) 未彻底研究小数据区，L(N,D) 在最小 D 处拟合差，未实验正则化与数据增强；(4) 使用 C ≈ 6NBS 未含 nctx 相关项，在 nctx ≳ 12·dmodel 时可能混淆；(5) 可能遗漏某些超参数调优（如初始化尺度、动量）；(6) 最优学习率对目标损失敏感。

## 相关工作与讨论要点

- 幂律来源广泛 [THK18]；密度估计 [Was06]、随机森林 [Bia12] 的幂律指数可粗略解释为数据中相关特征数的倒数。
- [HNA+17] 发现数据集随模型超线性增长，而本文发现次线性。
- 与 [Kom19]、EfficientNet [TL19]、[RRBS19b]、[RRBS19a] 相关；[VWB16] 深模型作为浅模型集成；[ZK16] 宽 vs 深 ResNet。
- [AS17, BHMM18] 过参数化泛化与 "jamming transition" [GJS+19]（本文未观察到该转变）。
- [JGH18, LXS+19] 大宽度展开；[ZLN+19] 噪声二次模型；Hessian 谱 [Pap18, GKX19, GARD18]。
- 缩放关系类比理想气体定律；推测适用于其他最大似然生成建模任务（图像、音频、视频、随机网络蒸馏）。
- 强调 "more is different"——平滑的损失改进可能掩盖定性能力跃迁；"Big models may be more important than big data"。
- 模型并行：pipelining [HCC+18]、宽网络并行 [SCP+18]、稀疏/分支 [CGRS19, GRK17, KSH12]、网络增长 [WRH17, WYL19]。

## 全文表格清单

全文含 6 张数据表：表 1（Transformer 参数与计算量计数，第 7 页）、表 2（L(N, D) 拟合，第 11 页）、表 3（L(N, S) 拟合，第 14 页）、表 4（关键趋势方程，第 20 页）、表 5（趋势拟合关键参数，第 20 页）、表 6（计算高效训练趋势，第 20 页）。

## 开放问题

- 缩放定律失效点是否具有"最大性能"深层含义；L* 是否为自然语言熵。
- 缩放关系是否适用于其他生成建模任务；是否存在底层统计力学理论。
- 最优分配指数是否在更大规模持续。
- Lmin 未知导致 Bcrit 参数化外推可靠性。
- 幂律在零损失前的失效点。
- Bcrit(L) 在实验范围外的预测可靠性。
- 小数据区拟合差，正则化/数据增强是否改变结论。
- C ≈ 6NBS 忽略 nctx 项在极大 nctx 时的混淆。
- 学习率经验公式在 N > 10^10 时失效。
- 上下文位置幂律是否源于语言本身幂律相关性，还是架构/优化的普遍特征。

## 相关页面

- [[openai]] — 作者所属机构
- [[gpt-3]] — 后续工作，本文缩放定律为其训练策略提供理论依据
- [[transformer]] — 本文研究的模型架构
- [[scaling-laws-for-neural-language-models神经语言模型缩放定律]] — 本文提出的核心概念
- [[幂律缩放]] — 本文的核心方法论
- [[临界batch-size]] — 本文提出的关键量
- [[计算高效前沿]] — 本文推导的最优分配模型
- [[非嵌入参数量]] — 本文的关键定义
- [[webtext2]] — 本文主数据集
- [[adam]]、[[adafactor]] — 本文使用的优化器
- [[缩放定律失效点]] — 本文的内在矛盾与猜想
- [[上下文位置幂律]] — 附录 D.5 的发现
- [[学习率调度无关性]] — 附录 D.6 的发现
- [[泛化对深度的独立性]] — 附录 D.8 的发现