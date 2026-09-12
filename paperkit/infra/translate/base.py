"""翻译后端的公共契约与重试策略。

Translator 用 Protocol 描述:services 层依赖这个协议而不是具体后端,因此
测试可以注入一个假翻译器,零网络、零打桩地跑完整条生成链路。
"""

import re
import time
from typing import Protocol

from ...errors import TranslateError


class Translator(Protocol):
    """翻译后端接口。实现只需把一段英文变成一段中文。"""

    name: str

    def translate(self, text: str) -> str: ...


def split_for_translate(text: str, limit: int = 1200) -> list[str]:
    """按句子边界把长段切成 ≤limit 的多块。

    翻译接口是 GET 请求,句子要拼进 URL,太长会被服务器拒绝。
    正则 (?<=[.!?;:]) + 在句读符号后面的空格处断开(lookbehind 不消耗字符)。
    """
    if len(text) <= limit:
        return [text]
    pieces, cur = [], ""
    for sent in re.split(r"(?<=[.!?;:]) +", text):
        if len(cur) + len(sent) + 1 > limit and cur:
            pieces.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        pieces.append(cur)
    return pieces


def protect_formulas(text: str) -> tuple[str, list[str]]:
    """把 $...$ / $$...$$ 换成占位符,返回 (替换后的文本, 原文列表)。

    翻译服务会改写 LaTeX 命令或符号,所以公式必须先摘出来,译完再原样还原。
    """
    formulas: list[str] = []

    def protect(match: re.Match) -> str:
        formulas.append(match.group(0))
        return f" __FORMULA_{len(formulas) - 1}__ "

    protected = re.sub(r"\$\$.*?\$\$|\$[^$\n]+\$", protect, text, flags=re.S)
    return protected, formulas


def retrying_translate(translator: Translator, text: str,
                       retries: int = 3) -> str:
    """翻译一段文本,带公式保护与重试;重试耗尽抛 TranslateError。

    失败必须抛异常而不是返回占位文本——调用方据此决定**不写缓存**,
    否则一次网络抖动会在缓存里留下永久伤疤,该段落再也不会被重试。
    """
    protected, formulas = protect_formulas(text)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            translated = translator.translate(protected)
            if not translated:
                raise ValueError("后端返回空译文")
            for i, formula in enumerate(formulas):
                translated = translated.replace(f"__FORMULA_{i}__", formula)
            return translated
        except Exception as e:          # KeyboardInterrupt 是 BaseException,不会在此被吞
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    raise TranslateError(f"翻译失败: {last_err}")
