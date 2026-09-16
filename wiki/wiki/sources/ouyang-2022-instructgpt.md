---
type: source
title: "Training Language Models to Follow Instructions with Human Feedback (Ouyang et al., 2022)"
tags: [rlhf, alignment, instruction-following, instructgpt, gpt-3, openai]
related:
  - "[[instructgpt]]"
  - "[[openai]]"
  - "[[gpt-3]]"
  - "[[rlhf基于人类反馈的强化学习]]"
  - "[[sft监督微调]]"
  - "[[reward-model奖励模型]]"
  - "[[ppo近端策略优化]]"
  - "[[alignment-tax对齐税]]"
  - "[[ppo-ptx]]"
  - "[[helpful-honest-harmless对齐目标]]"
  - "[[instruction-following指令遵循]]"
  - "[[truthfulqa]]"
  - "[[realtoxicityprompts]]"
  - "[[winogender]]"
  - "[[crows-pairs]]"
  - "[[flan]]"
  - "[[t0]]"
  - "[[perspective-api]]"
  - "[[openai-api-playground]]"
  - "[[6b-reward-model]]"
  - "[[langid-py]]"
  - "[[upwork]]"
  - "[[scaleai]]"
  - "[[in-context-learning上下文学习]]"
authors: [Long Ouyang, Jeff Wu, Xu Jiang, Diogo Almeida, Carroll L. Wainwright, Pamela Mishkin, Chong Zhang, Sandhini Agarwal, Katarina Slama, Alex Ray, John Schulman, Jacob Hilton, Fraser Kelton, Luke Miller, Maddie Simens, Amanda Askell, Peter Welinder, Paul Christiano, Jan Leike, Ryan Lowe]
year: 2022
url: "https://arxiv.org/abs/2203.02155"
venue: "arXiv preprint (arXiv:2203.02155v1 [cs.CL])"
created: 2026-09-16
updated: 2026-09-16
---

# Ouyang et al. 2022 - Training language models to follow instructions with human feedback

## 概述

本论文提出 **InstructGPT**：通过三阶段流程（SFT → Reward Model → PPO）用人类反馈微调 [[gpt-3]]，使语言模型的行为更符合用户意图。论文将 alignment 目标操作化为 helpful / honest / harmless（[[helpful-honest-harmless对齐目标]]），并系统评估了指令遵循、真实性、毒性、偏见与公开 NLP 数据集性能回退（[[alignment-tax对齐税]]）。

核心结论：**1.3B 参数的 InstructGPT 输出在人类评估中优于 175B GPT-3**；175B InstructGPT 相对 175B GPT-3 胜率 85±3%，相对 few-shot 175B GPT-3 胜率 71±4%。真实性提升、毒性下降，但偏见未显著改善。RLHF 带来 alignment tax，可通过 [[ppo-ptx]] 缓解。公开 NLP 数据集（[[flan]]、[[t0]]）不能反映模型实际使用方式。

论文标识：arXiv:2203.02155v1 [cs.CL] 4 Mar 2022。代码发布：https://github.com/openai/following-instructions-human-feedback

## 三阶段方法

1. **Step 1 — SFT**：收集标注员示范数据，监督微调预训练 GPT-3（[[sft监督微调]]）。
2. **Step 2 — Reward Model**：收集模型输出之间的比较数据，训练奖励模型（[[reward-model奖励模型]]）。
3. **Step 3 — PPO**：用 [[ppo近端策略优化]] 针对 RM 优化策略。Step 2 与 Step 3 可迭代进行。

### 奖励模型损失（公式 1）

```
loss(θ) = − (1 / C(K,2)) E_(x,yw,yl)∼D [ log( σ( rθ(x, yw) − rθ(x, yl) ) ) ]
```

其中 rθ(x, y) 为奖励模型对 prompt x 与 completion y 的标量输出，yw 为 yw 与 yl 中更受偏好的 completion，D 为人类比较数据集。

### RL 组合目标函数（公式 2）

```
objective (φ) = E_(x,y)∼D_πRL_φ [ rθ(x, y) − β log πRL_φ(y | x)/πSFT(y | x) ] + γ E_(x∼D_pretrain) [ log(πRL_φ(x)) ]
```

其中 πRL_φ 为学习到的 RL 策略，πSFT 为监督训练模型，D_pretrain 为预训练分布；β 为 KL reward 系数，γ 为预训练损失系数；对 "PPO" 模型 γ=0；除非另有说明，论文中 InstructGPT 指 PPO-ptx 模型。

## 数据集与人类数据

- prompt 主要来自 [[openai-api-playground]]（早期 InstructGPT 模型），按 user ID 划分 train/val/test，去重（长公共前缀）、每用户上限 200 条、训练集过滤 PII；不使用生产 API 客户数据。
- 首批 InstructGPT 由标注员自写 prompt（Plain / Few-shot / User-based 三类）。
- 约 40 名 [[upwork]] / [[scaleai]] 承包商；有筛选测试；训练时优先 helpfulness，最终评估时优先 truthfulness 与 harmlessness。
- 标注员间一致率：训练组 72.6±1.5%、留出组 77.3±1.3%（对比 Stiennon et al. 2020 研究者间 73±4%）。
- 数据集 >96% 为英文（[[langid-py]] 分类，实际比例估计 ≥99%）。

### Table 1: Distribution of use case categories from our API prompt dataset

| Use-case (%) | |
|---|---|
| Generation | 45.6% |
| Open QA | 12.4% |
| Brainstorming | 11.2% |
| Chat | 8.4% |
| Rewrite | 6.6% |
| Summarization | 4.2% |
| Classification | 3.5% |
| Other | 3.5% |
| Closed QA | 2.6% |
| Extract | 1.9% |

### Table 2: Illustrative prompts from our API prompt dataset

| Use-case | Prompt |
|---|---|
| Brainstorming | List five ideas for how to regain enthusiasm for my career |
| Generation | Write a short story where a bear goes to the beach, makes friends with a seal, and then returns home. |
| Rewrite | This is the summary of a Broadway play: `""" {summary} """` This is the outline of the commercial for that play: `"""` |

### Table 3: Labeler-collected metadata on the API distribution

| Metadata | Scale |
|---|---|
| Overall quality | Likert scale; 1-7 |
| Fails to follow the correct instruction / task | Binary |
| Inappropriate for customer assistant | Binary |
| Hallucination | Binary |
| Satisifies constraint provided in the instruction | Binary |
| Contains sexual content | Binary |
| Contains violent content | Binary |
| Encourages or fails to discourage violence/abuse/terrorism/self-harm | Binary |
| Denigrates a protected class | Binary |
| Gives harmful advice | Binary |
| Expresses opinion | Binary |
| Expresses moral judgment | Binary |

### Table 6: Dataset sizes, in terms of number of prompts

| SFT Data | | | RM Data | | | PPO Data | | |
|---|---|---|---|---|---|---|---|---|
| split | source | size | split | source | size | split | source | size |
| train | labeler | 11,295 | train | labeler | 6,623 | train | customer | 31,144 |
| train | customer | 1,430 | train | customer | 26,584 | valid | customer | 16,185 |
| valid | labeler | 1,550 | valid | labeler | 3,488 | | | |
| valid | customer | 103 | valid | customer | 14,399 | | | |

### Table 7: Dataset annotations

| Annotation | RM test | RM train | RM valid | SFT train | SFT valid |
|---|---|---|---|---|---|
| Ambiguous | – | 7.9% | 8.0% | 5.1% | 6.4% |
| Sensitive content | – | 6.9% | 5.3% | 0.9% | 1.0% |
| Identity dependent | – | – | – | 0.9% | 0.3% |
| Closed domain | 11.8% | 19.4% | 22.9% | 27.4% | 40.6% |
| Continuation style | – | 15.5% | 16.2% | 17.9% | 21.6% |
| Requests opinionated content | 11.2% | 7.7% | 7.5% | 8.6% | 3.4% |
| Requests advice | 3.9% | – | – | – | – |
| Requests moral judgment | 0.8% | 1.1% | 0.3% | 0.3% | 0.0% |
| Contains explicit safety constraints | – | 0.4% | 0.4% | 0.3% | 0.0% |
| Contains other explicit constraints | – | 26.3% | 28.9% | 25.6% | 20.7% |
| Intent unclear | 7.9% | – | – | – | – |

### Table 8: Average prompts per customer

| Model | Split | Prompts per customer |
|---|---|---|
| SFT | train | 1.65 |
| SFT | valid | 1.87 |
| RM | train | 5.35 |
| RM | valid | 27.96 |
| PPO | train | 6.01 |
| PPO | valid | 31.55 |
| – | test | 1.81 |

### Table 9: Prompt lengths by dataset

| Model | Split | Count | Mean | Std | Min | 25% | 50% | 75% | Max |
|---|---|---|---|---|---|---|---|---|---|
| SFT | train | 12725 | 408 | 433 | 1 | 37 | 283 | 632 | 2048 |
| SFT | valid | 1653 | 401 | 433 | 4 | 41 | 234 | 631 | 2048 |
| RM | train | 33207 | 199 | 334 | 1 | 20 | 64 | 203 | 2032 |
| RM | valid | 17887 | 209 | 327 | 1 | 26 | 77 | 229 | 2039 |
| PPO | train | 31144 | 166 | 278 | 2 | 19 | 62 | 179 | 2044 |
| PPO | valid | 16185 | 186 | 292 | 1 | 24 | 71 | 213 | 2039 |
| – | test set | 3196 | 115 | 194 | 1 | 17 | 49 | 127 | 1836 |

### Table 10: Prompt lengths by category

| Category | Count | Mean | Std | Min | 25% | 50% | 75% | Max |
|---|---|---|---|---|---|---|---|---|
| Brainstorming | 5245 | 83 | 149 | 4 | 17 | 36 | 85 | 1795 |
| Chat | 3911 | 386 | 376 | 1 | 119 | 240 | 516 | 1985 |
| Classification | 1615 | 223 | 318 | 6 | 68 | 124 | 205 | 2039 |
| Extract | 971 | 304 | 373 | 3 | 74 | 149 | 390 | 1937 |
| Generation | 21684 | 130 | 223 | 1 | 20 | 52 | 130 | 1999 |
| QA, closed | 1398 | 325 | 426 | 5 | 68 | 166 | 346 | 2032 |
| QA, open | 6262 | 89 | 193 | 1 | 10 | 18 | 77 | 1935 |
| Rewrite | 3168 | 183 | 237 | 4 | 52 | 99 | 213 | 1887 |
| Summarization | 1962 | 424 | 395 | 6 | 136 | 284 | 607 | 1954 |
| Other | 1767 | 180 | 286 | 1 | 20 | 72 | 188 | 1937 |

### Table 11: Prompt and demonstration lengths

| Prompt source | Measurement | Count | Mean | Std | Min | 25% | 50% | 75% | Max |
|---|---|---|---|---|---|---|---|---|---|
| Contractor | prompt length | 12845 | 437 | 441 | 5 | 42 | 324 | 673 | 2048 |
| Contractor | demo length | 12845 | 38 | 76 | 1 | 9 | 18 | 41 | 2048 |
| Customer | prompt length | 1533 | 153 | 232 | 1 | 19 | 67 | 186 | 1937 |
| Customer | demo length | 1533 | 88 | 179 | 0 | 15 | 39 | 88 | 2048 |

### Table 12: Labeler demographic data

| 问题 | 选项 | 比例 |
|------|------|------|
| Gender | Male | 50.0% |
| | Female | 44.4% |
| | Nonbinary / other | 5.6% |
| Ethnicity | White / Caucasian | 31.6% |
| | Southeast Asian | 52.6% |
| | Indigenous / Native American / Alaskan Native | 0.0% |
| | East Asian | 5.3% |
| | Middle Eastern | 0.0% |
| | Latinx | 15.8% |
| | Black / of African descent | 10.5% |
| Nationality | Filipino | 22% |
| | Bangladeshi | 22% |
| | American | 17% |
| | Albanian | 5% |
| | Brazilian | 5% |
| | Canadian | 5% |
| | Colombian | 5% |
| | Indian | 5% |
| | Uruguayan | 5% |
| | Zimbabwean | 5% |
| Age | 18-24 | 26.3% |
| | 25-34 | 47.4% |
| | 35-44 | 10.5% |
| | 45-54 | 10.5% |
| | 55-64 | 5.3% |
| | 65+ | 0% |
| Education | Less than high school degree | 0% |
| | High school degree | 10.5% |
| | Undergraduate degree | 52.6% |
| | Master's degree | 36.8% |
| | Doctorate degree | 0% |

### Table 13: Labeler satisfaction survey

| 陈述 | Strongly agree | Agree | Neither | Disagree | Strongly disagree |
|------|------|------|------|------|------|
| It was clear from the instructions what I was supposed to do. | 57.9% | 42.1% | 0% | 0% | 0% |
| I found the task enjoyable and engaging. | 57.9% | 36.8% | 5.3% | 0% | 0% |
| I found the task repetitive. | 0% | 31.6% | 31.6% | 36.8% | 0% |
| I was paid fairly for doing the task. | 47.4% | 42.1% | 10.5% | 0% | 0% |
| Overall, I'm glad I did this task. | 78.9% | 21.1% | 0% | 0% | 0% |

### Table 14: Automatic evaluations

| Task | Metric | Prompt | GPT XL | GPT 6b | GPT 175b | SFT XL | SFT 6b | SFT 175b | PPO XL | PPO 6b | PPO 175b | PPO+ptx XL | PPO+ptx 6b | PPO+ptx 175b |
|------|--------|--------|--------|--------|----------|--------|--------|----------|--------|--------|----------|------------|------------|--------------|
| Winogender | entropy | basic | 0.750 | 0.721 | 0.735 | 0.583 | 0.535 | 0.503 | 0.698 | 0.587 | 0.618 | 0.760 | 0.719 | 0.737 |
| Winogender | entropy | respectful | 0.774 | 0.753 | 0.796 | 0.561 | 0.446 | 0.479 | 0.644 | 0.562 | 0.527 | 0.608 | 0.585 | 0.696 |
| Winogender | entropy | biased | 0.760 | 0.773 | 0.783 | 0.561 | 0.516 | 0.540 | 0.706 | 0.567 | 0.564 | 0.676 | 0.543 | 0.690 |
| CrowS Pairs | entropy | basic | 0.448 | 0.430 | 0.410 | 0.356 | 0.326 | 0.241 | 0.355 | 0.361 | 0.326 | 0.448 | 0.434 | 0.413 |
| CrowS Pairs | entropy | respectful | 0.419 | 0.413 | 0.362 | 0.302 | 0.260 | 0.204 | 0.281 | 0.258 | 0.270 | 0.310 | 0.273 | 0.243 |
| CrowS Pairs | entropy | biased | 0.420 | 0.419 | 0.353 | 0.305 | 0.252 | 0.187 | 0.287 | 0.288 | 0.223 | 0.314 | 0.254 | 0.205 |
| Real Toxicity | toxicity | basic | 0.228 | 0.229 | 0.231 | 0.198 | 0.211 | 0.211 | 0.213 | 0.214 | 0.228 | 0.228 | 0.227 | 0.234 |
| Real Toxicity | toxicity | respectful | 0.211 | 0.232 | 0.233 | 0.196 | 0.196 | 0.199 | 0.198 | 0.176 | 0.205 | 0.179 | 0.204 | 0.196 |
| Real Toxicity | toxicity | biased | 0.250 | 0.261 | 0.285 | 0.236 | 0.250 | 0.256 | 0.254 | 0.382 | 0.427 | 0.263 | 0.512 | 0.400 |
| Truthful QA | true | QA prompt | 0.312 | 0.220 | 0.284 | 0.324 | 0.436 | 0.515 | 0.546 | 0.586 | 0.755 | 0.297 | 0.476 | 0.712 |
| Truthful QA | true | instruction | 0.340 | 0.414 | 0.570 | 0.360 | 0.756 | 0.665 | 0.634 | 0.928 | 0.879 | 0.355 | 0.733 | 0.815 |
| Truthful QA | true | QA + instruct | 0.335 | 0.348 | 0.438 | 0.517 | 0.659 | 0.852 | 0.807 | 0.760 | 0.944 | 0.322 | 0.494 | 0.610 |
| Truthful QA | true + info | QA prompt | 0.193 | 0.186 | 0.251 | 0.267 | 0.253 | 0.271 | 0.524 | 0.574 | 0.752 | 0.285 | 0.464 | 0.689 |
| Truthful QA | true + info | instruction | 0.212 | 0.212 | 0.226 | 0.282 | 0.213 | 0.257 | 0.559 | 0.187 | 0.382 | 0.339 | 0.350 | 0.494 |
| Truthful QA | true + info | QA + instruct | 0.218 | 0.267 | 0.242 | 0.288 | 0.319 | 0.206 | 0.789 | 0.704 | 0.588 | 0.242 | 0.399 | 0.315 |
| HellaSwag | accuracy | zero-shot | 0.549 | 0.673 | 0.781 | 0.528 | 0.672 | 0.753 | 0.507 | 0.646 | 0.743 | 0.552 | 0.690 | 0.807 |
| HellaSwag | accuracy | few-shot | 0.550 | 0.677 | 0.791 | 0.516 | 0.657 | 0.741 | 0.530 | 0.671 | 0.759 | 0.559 | 0.694 | 0.820 |
| WSC | accuracy | zero-shot | 0.567 | 0.635 | 0.740 | 0.615 | 0.606 | 0.654 | 0.663 | 0.654 | 0.683 | 0.692 | 0.587 | 0.731 |
| WSC | accuracy | few-shot | 0.587 | 0.654 | 0.798 | 0.615 | 0.625 | 0.779 | 0.625 | 0.596 | 0.654 | 0.644 | 0.673 | 0.788 |
| RTE | accuracy | zero-shot | 0.527 | 0.617 | 0.563 | 0.487 | 0.516 | 0.570 | 0.480 | 0.708 | 0.704 | 0.538 | 0.657 | 0.668 |
| RTE | accuracy | few-shot | 0.585 | 0.682 | 0.614 | 0.574 | 0.657 | 0.700 | 0.606 | 0.585 | 0.711 | 0.545 | 0.697 | 0.765 |
| SST | accuracy | zero-shot | 0.592 | 0.616 | 0.898 | 0.873 | 0.888 | 0.907 | 0.817 | 0.820 | 0.920 | 0.812 | 0.901 | 0.900 |
| SST | accuracy | few-shot | 0.842 | 0.930 | 0.944 | 0.909 | 0.933 | 0.936 | 0.794 | 0.880 | 0.944 | 0.838 | 0.923 | 0.938 |
| QuAC | f1 | zero-shot | 32.13 | 38.19 | 42.55 | 34.52 | 41.19 | 45.22 | 29.02 | 37.64 | 34.52 | 35.04 | 37.35 | 41.60 |
| QuAC | f1 | few-shot | 36.02 | 41.78 | 45.38 | 35.95 | 43.13 | 48.77 | 31.81 | 40.63 | 36.00 | 39.40 | 42.42 | 46.99 |
| SQuADv2 | f1 | zero-shot | 51.97 | 58.66 | 64.30 | 36.88 | 46.53 | 57.67 | 45.37 | 47.42 | 43.68 | 45.46 | 47.23 | 59.85 |
| SQuADv2 | f1 | few-shot | 58.86 | 62.33 | 69.75 | 46.62 | 53.91 | 65.90 | 48.11 | 52.34 | 51.95 | 58.33 | 63.78 | 69.93 |
| DROP | f1 | zero-shot | 17.68 | 19.96 | 27.53 | 13.29 | 13.23 | 15.79 | 14.70 | 12.34 | 13.08 | 14.71 | 10.64 | 15.23 |
| DROP | f1 | few-shot | 25.43 | 30.08 | 35.27 | 23.84 | 30.99 | 35.85 | 21.61 | 27.11 | 27.78 | 23.89 | 29.39 | 33.34 |
| FR → EN 15 | BLEU | zero-shot | 30.65 | 34.99 | 38.92 | 25.56 | 33.25 | 36.90 | 19.85 | 25.22 | 24.16 | 25.77 | 30.41 | 34.28 |
| FR → EN 15 | BLEU | few-shot | 31.37 | 35.49 | 39.93 | 24.73 | 31.76 | 35.07 | 21.65 | 29.96 | 26.58 | 27.67 | 33.56 | 36.76 |
| CNN/DM | ROUGE-L | — | 0.182 | 0.197 | 0.196 | 0.198 | 0.235 | 0.225 | 0.218 | 0.231 | 0.227 | 0.214 | 0.231 | 0.220 |
| TLDR | ROUGE-L | — | 0.182 | 0.197 | 0.196 | 0.198 | 0.235 | 0.225 | 0.218 | 0.231 | 0.227 | 0.214 | 0.231 | 0.220 |

## 关键超参数

```
SFT: 16 epochs, residual dropout 0.2, cosine LR → 10%, no warmup
  1.3B/6B: LR 9.65e-6, batch 32
  175B:    LR 5.03e-6, batch 8

RM: 6B, 1 epoch, LR 9e-6, cosine → 10%, batch 64
  K = 4..9 completions per prompt, ties dropped
  max comparisons per batch = 64 × C(K,2) ≤ 2,304

RLHF init: SFT 2 epochs on demonstrations + 10% pretraining mix
  1.3B/6B batch 32, 175B batch 8
  final LR: 1.3B=5e-6, 6B=1.04e-5, 175B=2.45e-6

RLHF: 256k episodes, ~31k unique prompts, β=0.02 (KL)
  batch 512, minibatch 64 (8 minibatches, 1 inner epoch)
  constant LR, warmup 10 iters (start at 1/10 peak)
  EMA decay 0.992, GAE no discount, PPO clip 0.2, sampling temp 1
  value function LR: 1.3B/6B=9e-6, 175B=5e-6
  pretraining mix: 8× RL episodes, γ=27.8

FLAN/T0: 175B GPT-3 fine-tune, cosine → 10%, batch 64
  FLAN: LR 4e-6, 896k examples (selected)
  T0: subsampled to 1M; selected batch 128/LR 4e-6/896k

Adam: β1=0.9, β2=0.95
Context length 2k tokens; filter prompts >1k; max response 1k
```

## 主要结果

- 175B InstructGPT vs GPT-3 胜率 85±3%；vs few-shot GPT-3 胜率 71±4%。
- 1.3B InstructGPT 输出被偏好于 175B GPT-3（100x 参数差距）。
- TruthfulQA 上真实性约 2x；闭域幻觉率 21% vs 41%。
- RealToxicityPrompts 上毒性输出减少约 25%（在 "be respectful" 提示下）；去掉该指令后优势消失；显式要求有毒输出时 InstructGPT 反而更毒。
- Winogender、CrowS-Pairs 上无显著改善（偏见未改善）。
- 公开数据集性能回退（SQuAD、DROP、HellaSwag、WMT 2015 Fr→En），PPO-ptx 可缓解；DROP、SQuADv2、翻译上仍落后 GPT-3。
- 对 held-out labelers 泛化良好；RM 5-fold 交叉验证：组间 72.4±0.4%、组内 69.6±0.9%。
- FLAN/T0 优于默认 GPT-3、与 few-shot GPT-3 相当、差于 SFT 基线；175B InstructGPT vs FLAN 胜率 78±4%，vs T0 胜率 79±4%。
- 计算成本：175B SFT 4.9 petaflops/s-days；175B PPO-ptx 60 petaflops/s-days；GPT-3 3,640 petaflops/s-days。

## 定性结果与简单错误

- InstructGPT 对 RLHF 微调分布之外的指令展现泛化：可跟随非英语指令、可做代码摘要与问答；但常以英语输出即使指令为其他语言。
- 三类简单错误：(1) 面对含虚假前提的指令会错误接受前提；(2) 过度 hedge，对简单问题给出多答案；(3) 指令含多个显式约束时性能下降。
- 附录 F（Figure 45–50）给出 labeler 撰写 prompt + 人工示范 + 未挑选补全的定性对比样本；prompt 轻度挑选（15 选 5）。InstructGPT 更贴合指令格式与意图，但并非总是正确（如代码语义描述有误）。

## 讨论与局限

- **5.2 我们在对齐谁**：对齐的是标注员（主要美国或东南亚英语使用者）、研究者/OpenAI 组织、OpenAI 客户，以及隐含的终端用户；这些群体都不代表所有受影响人群。
- **5.3 局限性**：模型既不完整对齐也不完全安全；仍生成有毒/偏见输出、编造事实；最大局限是多数情况下遵循用户指令，即使可能导致现实世界危害。
- **5.4 开放问题**：对抗式数据收集、预训练数据过滤、WebGPT 真实性方法、steerability/controllability、expert iteration、behavior cloning、constrained optimization、基于原则的 alignment（Gabriel 2020）。
- **5.5 更广泛影响**：alignment 技术不是解决 LLM 安全问题的万灵药；医疗诊断、受保护特征分类、信贷/就业/住房资格、政治广告、执法等领域应谨慎部署或完全不部署；开源 vs API 访问存在安全与权力集中化权衡。

## 相关页面

- 模型与组织：[[instructgpt]]、[[gpt-3]]、[[openai]]、[[6b-reward-model]]
- 方法与概念：[[rlhf基于人类反馈的强化学习]]、[[sft监督微调]]、[[reward-model奖励模型]]、[[ppo近端策略优化]]、[[ppo-ptx]]、[[alignment-tax对齐税]]、[[helpful-honest-harmless对齐目标]]、[[instruction-following指令遵循]]、[[in-context-learning上下文学习]]
- 数据集与工具：[[truthfulqa]]、[[realtoxicityprompts]]、[[winogender]]、[[crows-pairs]]、[[flan]]、[[t0]]、[[perspective-api]]、[[openai-api-playground]]、[[langid-py]]、[[upwork]]、[[scaleai]]