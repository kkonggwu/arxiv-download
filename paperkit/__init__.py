"""paperkit —— arXiv 论文下载与中英对照阅读材料生成。

分层结构(依赖方向自上而下单向,由 tests/test_layering.py 在 CI 层强制):

    cli/        命令行边界:解析参数、组装 Settings、决定退出码
    services/   应用层:编排用例(download / bilingual / images)
    domain/     领域层:纯规则与纯渲染,零副作用
    infra/      基础设施:http / storage / cache / translate / logging
    config.py   配置:唯一的 frozen Settings
    errors.py   异常层级

对外主要入口是 `paperkit.cli.main`,以及各层的稳定 API:
    from paperkit.services import build_bilingual
    from paperkit.domain import parse_arxiv_id
    from paperkit.config import Settings
"""

__all__ = ["cli", "config", "domain", "errors", "infra", "services", "storage"]
