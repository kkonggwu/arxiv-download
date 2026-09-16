---
type: entity
title: WebText2
tags: [dataset, corpus, language-model, openai]
related:
  - "[[openai]]"
  - "[[scaling-laws-for-neural-language-models神经语言模型缩放定律]]"
  - "[[非嵌入参数量]]"
  - "[[kaplan-2020-scaling-laws-for-neural-language-models]]"
created: 2026-09-16
updated: 2026-09-16
---

# WebText2

WebText2 是本文训练与评估 Transformer 语言模型的主数据集，为 WebText 的扩展版本，由 [[openai]] 构建。

## 构成与规模

- 来源：Reddit 外链，包含 2017-12 之前的链接以及 2018-01 至 2018-10 的链接，要求帖子获得 ≥3 karma。
- 提取工具：Newspaper3k。
- 规模：20.3M 文档、96 GB、1.62×10^10 词、2.29×10^10 tokens。
- 测试集：6.6×10^8 tokens。
- 分词：BPE 词表大小 50257；统计为 1.4 tokens/word、4.3 characters/token。

## 在本文中的作用

- 作为主训练与测试分布，用于拟合 [[scaling-laws-for-neural-language-models神经语言模型缩放定律]] 中的 L(N)、L(D)、L(Cmin) 等幂律。
- 本文发现 <10^9 参数模型可在 22B token WebText2 上几乎无过拟合，最大模型出现轻微过拟合。
- 与 Books Corpus、Common Crawl、English Wikipedia、Internet Books 一起作为额外测试分布，用于验证跨分布泛化仅依赖 in-distribution 验证损失。

## 相关页面

- [[openai]] — 数据集构建方
- [[scaling-laws-for-neural-language-models神经语言模型缩放定律]] — 使用该数据集拟合的核心规律