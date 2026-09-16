---
type: entity
title: OpenAI
tags: [organization, research-lab, gpt-3, gpt-2, ai-lab, language-model]
related:
  - "[[gpt-3]]"
  - "[[gpt-2]]"
  - "[[in-context-learning上下文学习]]"
  - "[[scaling-laws-for-neural-language-models神经语言模型缩放定律]]"
  - "[[webtext2]]"
  - "[[brown-2020-language-models-are-few-shot-learners]]"
  - "[[kaplan-2020-scaling-laws-for-neural-language-models]]"
created: 2026-09-16
updated: 2026-09-16
---

# OpenAI

OpenAI 是 [[gpt-3]] 与 [[gpt-2]] 的开发者，也是多篇大规模语言模型研究论文的作者所属机构。本页汇总该机构在两份来源文献中的角色：

| 来源文献 | OpenAI 的角色 |
| --- | --- |
| 《Language Models are Few-Shot Learners》([[gpt-3]] 论文) | 论文所属机构；GPT-3 与 GPT-2 的开发者 |
| 《Scaling Laws for Neural Language Models》 | 全部作者的所属或合作机构；提供研究环境、计算资源与数据集 |

## 在《Language Models are Few-Shot Learners》中的角色

- 训练并发布 GPT-3（175B 参数自回归语言模型）。
- 论文作者团队包括 Tom B. Brown、Benjamin Mann、Nick Ryder、Melanie Subbiah、Jared Kaplan、Sam McCandlish、Alec Radford、Ilya Sutskever、Dario Amodei 等 31 人。
- 致谢对象包括 Ryan Lowe、Jakub Pachocki、Szymon Sidor、Greg Brockman、Michael Petrov、Brooke Chan、Chelsea Voss、David Luan、Irene Solaiman、Harrison Edwards、Yura Burda、Geoffrey Irving、Paul Christiano、Long Ouyang、Chris Hallacy、Shan Carter 等。
- 论文承诺发布合成数据集（算术、词解扰、SAT 类比等）以及 500 条未筛选的无条件文本样本。
- 论文中提及 OpenAI Dota Team 作为引用来源之一。

## 在《Scaling Laws for Neural Language Models》中的角色

- OpenAI 是本文全部作者的所属或合作机构。本文作者包括 Jared Kaplan（Johns Hopkins University / OpenAI）、Sam McCandlish、Tom Henighan、Tom B. Brown、Benjamin Chess、Rewon Child、Scott Gray、Alec Radford、Jeffrey Wu、Dario Amodei。
- 提供研究环境与计算资源，完成全部 Transformer 语言模型训练实验。
- 构建并维护 [[webtext2]] 数据集。
- 本文的缩放定律结论直接支撑了 OpenAI 后续 [[gpt-3]] 等大模型的训练策略（固定计算预算下训练超大模型并提前停止）。
- 致谢名单中的 Shan Carter、Paul Christiano、Jack Clark、Ajeya Cotra、Ethan Dyer、Jason Eisner、Danny Hernandez、Jacob Hilton、Brice Menard、Chris Olah、Ilya Sutskever 亦与 OpenAI 相关。

## 两份来源中的重合人员

两篇论文的作者 / 致谢名单存在部分重名。以下按来源分别标注，不代表两份名单的构成相同：

| 姓名 | 《Language Models are Few-Shot Learners》 | 《Scaling Laws for Neural Language Models》 |
| --- | --- | --- |
| Tom B. Brown | 作者 | 作者 |
| Jared Kaplan | 作者 | 作者（Johns Hopkins University / OpenAI） |
| Sam McCandlish | 作者 | 作者 |
| Alec Radford | 作者 | 作者 |
| Dario Amodei | 作者 | 作者 |
| Ilya Sutskever | 作者 | 致谢 |
| Shan Carter | 致谢 | 致谢 |
| Paul Christiano | 致谢 | 致谢 |

## 相关页面

- [[gpt-3]] — OpenAI 发布的大规模语言模型；亦为《Language Models are Few-Shot Learners》论文主题
- [[gpt-2]] — OpenAI 开发的语言模型
- [[scaling-laws-for-neural-language-models神经语言模型缩放定律]] — 《Scaling Laws for Neural Language Models》提出的核心概念
- [[webtext2]] — OpenAI 构建并维护的数据集
- [[brown-2020-language-models-are-few-shot-learners]]