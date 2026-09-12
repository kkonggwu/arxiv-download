"""paperkit 的异常层级。

设计要点是**区分「可重试」与「不可重试」**。重构前所有失败都是 RuntimeError,
调用方无法判断一次失败是网络抖动(重跑就好)还是这篇论文根本没有 HTML 版
(重跑一万次也一样),只能一律记为失败。

    PaperKitError
    ├── ConfigError          参数/环境变量非法
    ├── NetworkError         连接/超时/5xx,重试耗尽 —— 可重试
    ├── SourceUnavailable    arXiv 与 ar5iv 都没有 HTML —— 不可重试
    ├── ParseError           HTML 结构异常,抽不出区块
    ├── TranslateError       单段翻译失败 —— 可重试
    ├── RegistryError        papers.json 读写或格式错误
    └── AssetError           单张插图失败(可降级,不中断整篇)
"""


class PaperKitError(Exception):
    """本工具所有可预期错误的基类。CLI 统一捕获它并决定退出码。"""


class ConfigError(PaperKitError):
    """命令行参数或环境变量非法(退出码 3)。"""


class NetworkError(PaperKitError):
    """网络层失败且重试已耗尽。调用方可以放心重试。"""


class SourceUnavailable(PaperKitError):
    """两个 HTML 源都拿不到正文(如纯扫描版 PDF)。

    与 NetworkError 的区别在于**重试没有意义**,批量任务应当直接跳过并
    在汇总里单独计数,而不是无谓地重试到超时。
    """


class ParseError(PaperKitError):
    """HTML 结构不符合预期,解析不出区块。"""


class TranslateError(PaperKitError):
    """单段翻译失败(重试若干次后仍失败)。

    必须抛异常而不是返回占位文本:调用方据此决定**不写缓存**,否则一次
    网络抖动会在缓存里留下永久伤疤,该段落再也不会被重试。
    """


class RegistryError(PaperKitError):
    """papers.json 读写失败或内容格式不对。"""


class AssetError(PaperKitError):
    """单张插图下载失败。调用方应降级为绝对链接,不中断整篇。"""
