"""术语表与机翻缩写纠错。

这些表只在「写出 Markdown 时」生效,不参与缓存——因此以后扩充词条,
老缓存不用重新翻译,重跑一遍就能全部修正。
"""

# 常见章节名固定译法,避免逐词机翻产生"抽象的"这类笑话
SECTION_ZH = {
    "Abstract": "摘要", "Introduction": "引言", "Conclusion": "结论",
    "Conclusions": "结论", "Discussion": "讨论", "Acknowledgments": "致谢",
    "Acknowledgements": "致谢", "References": "参考文献", "Appendix": "附录",
    "Related Work": "相关工作", "Conclusion and Future Work": "结论与展望",
    "Experiments": "实验", "Experimental Setup": "实验设置",
    "Limitations": "局限性", "Ethics Statement": "伦理声明",
    "Broader Impact": "更广泛的影响", "Background": "背景",
}

# 机翻缩写纠错:Google 会把 LLM(s) 译成"法学硕士"等,输出时替换。
# 注意必须在"写出 Markdown 时"替换而非缓存时——这样以后扩充词条,
# 老缓存不用重新翻译,重跑一遍就能全部修正。
ACRONYM_FIX = {
    "法学硕士们": "大语言模型", "法学硕士": "大语言模型",
    "大型语言模型(大语言模型)": "大语言模型",
    "提示工程学": "提示工程", "提示词工程学": "提示工程",
}


def fix_acronyms(zh: str) -> str:
    """对译文做缩写纠错(顺序遍历替换表)。"""
    for bad, good in ACRONYM_FIX.items():
        zh = zh.replace(bad, good)
    return zh
