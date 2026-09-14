"""架构护栏:把依赖方向写成 CI 会红的测试。

设计方案里的依赖矩阵如果只靠自觉遵守,半年后必然失守。这里用 AST 直接
检查每个模块的 import,把「domain 不许碰网络」「cli 不许绕过 services」
这类约束变成可执行的断言。

不引入 import-linter 之类的第三方依赖——这个项目的硬约束是运行时零依赖,
测试也不该例外。
"""

import ast
import unittest
from pathlib import Path

from tests.helpers import bootstrap  # noqa: F401

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "paperkit"

# 每个分层允许依赖哪些层
ALLOWED: dict[str, set[str]] = {
    "errors": {"errors"},
    "config": {"config", "errors"},
    "domain": {"domain", "errors"},
    "infra": {"infra", "domain", "config", "errors"},
    "services": {"services", "infra", "domain", "config", "errors"},
    "cli": {"cli", "services", "config", "errors"},
    # 包根(__init__ / __main__):只做装配
    "root": {"root", "errors", "config", "domain", "infra", "services", "cli"},
}

# 跨切面例外:日志是表现层的天然依赖,不算「cli 越过 services 摸基础设施」。
# 精确到模块,避免这个口子被用来放行 http_get / write_text 之类。
ALLOWED_MODULES: dict[str, set[str]] = {
    "cli": {"paperkit.infra.logging"},
}

LAYER_DIRS = ("domain", "infra", "services", "cli")


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(PROJECT_ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _layer(path: Path) -> str:
    rel = path.relative_to(SRC)
    if rel.parts[0] in LAYER_DIRS:
        return rel.parts[0]
    if rel.name in ("__init__.py", "__main__.py"):
        return "root"
    return rel.stem               # errors / config


def _layer_of_module(dotted: str) -> str:
    parts = dotted.split(".")
    if len(parts) >= 3 and parts[1] in LAYER_DIRS:
        return parts[1]
    return parts[-1]


def _resolve(module: str, is_package: bool, level: int,
             node_module: str | None) -> str | None:
    """把(可能是相对的)import 解析成绝对模块名。

    包内 __init__.py 的「当前包」是模块名本身,普通模块则是它的父包——
    这一处不区分清楚,`from .main import x` 会被误判成依赖 paperkit.main。
    """
    if level == 0:
        return node_module
    current = module if is_package else module.rpartition(".")[0]
    parts = current.split(".")
    up = level - 1
    if up > len(parts):
        return None
    base = parts[:len(parts) - up] if up else parts
    if node_module:
        base = base + node_module.split(".")
    return ".".join(base)


def _imported_targets(path: Path) -> list[tuple[str, int]]:
    """返回 [(paperkit 内部的绝对模块名, 行号), ...]。"""
    module = _module_name(path)
    is_package = path.name == "__init__.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            target = _resolve(module, is_package, node.level, node.module)
            if target and target.startswith("paperkit"):
                out.append((target, node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("paperkit"):
                    out.append((alias.name, node.lineno))
    return out


class TestDependencyDirection(unittest.TestCase):
    def test_no_illegal_cross_layer_import(self):
        violations = []
        for path in sorted(SRC.rglob("*.py")):
            layer = _layer(path)
            for target, lineno in _imported_targets(path):
                if target in ALLOWED_MODULES.get(layer, set()):
                    continue
                dep = _layer_of_module(target)
                if dep not in ALLOWED[layer]:
                    violations.append(
                        f"{path.relative_to(PROJECT_ROOT)}:{lineno} "
                        f"{layer} 不得依赖 {dep}  ({target})")
        self.assertEqual(violations, [], "\n".join(violations))

    def test_every_layer_is_covered_by_the_matrix(self):
        seen = {_layer(p) for p in SRC.rglob("*.py")}
        self.assertTrue(seen <= set(ALLOWED),
                        f"有分层未登记到 ALLOWED: {seen - set(ALLOWED)}")

    def test_domain_is_depended_on_only_from_above(self):
        """domain 是叶子层,谁都能用;它自己不依赖任何内部层(除 errors)。"""
        for path in sorted((SRC / "domain").rglob("*.py")):
            for target, lineno in _imported_targets(path):
                dep = _layer_of_module(target)
                self.assertIn(dep, {"domain", "errors"},
                              f"{path.name}:{lineno} domain 只能依赖 "
                              f"domain/errors,实际依赖 {dep}")


class TestDomainPurity(unittest.TestCase):
    """domain 层是纯函数:不碰网络、不读写文件、不读环境变量。"""

    FORBIDDEN_MODULES = {"os", "urllib", "urllib.request", "socket", "shutil",
                         "tempfile", "subprocess", "json"}
    FORBIDDEN_CALLS = {"open", "urlopen", "read_text", "write_text",
                       "write_bytes", "read_bytes", "mkdir", "unlink"}

    def _domain_files(self):
        return sorted((SRC / "domain").rglob("*.py"))

    def test_domain_does_not_import_io_modules(self):
        violations = []
        for path in self._domain_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in self.FORBIDDEN_MODULES:
                            violations.append(
                                f"{path.name}:{node.lineno} import {alias.name}")
                elif (isinstance(node, ast.ImportFrom)
                      and node.module in self.FORBIDDEN_MODULES):
                    violations.append(
                        f"{path.name}:{node.lineno} from {node.module}")
        self.assertEqual(violations, [], "\n".join(violations))

    def test_domain_does_not_call_io_functions(self):
        violations = []
        for path in self._domain_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    fn = node.func
                    name = (fn.attr if isinstance(fn, ast.Attribute)
                            else getattr(fn, "id", None))
                    if name in self.FORBIDDEN_CALLS:
                        violations.append(f"{path.name}:{node.lineno} {name}()")
        self.assertEqual(violations, [], "\n".join(violations))


class TestNoMutableModuleGlobals(unittest.TestCase):
    """核心目标:不再有「由 main() 改写的模块级可变全局」。"""

    KNOWN_BAD = {"PROXY", "TRANSLATE_BACKEND", "OPENAI_BASE_URL",
                 "OPENAI_MODEL", "TRANSLATE_API_KEY"}

    def test_no_global_statement_remains(self):
        violations = []
        for path in sorted(SRC.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Global):
                    violations.append(
                        f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} "
                        f"global {', '.join(node.names)}")
        self.assertEqual(violations, [], "\n".join(violations))

    def test_legacy_config_globals_are_gone(self):
        hits = []
        for path in sorted(SRC.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id in self.KNOWN_BAD:
                            hits.append(f"{path.relative_to(PROJECT_ROOT)}"
                                        f":{node.lineno} {t.id}")
        self.assertEqual(hits, [], "\n".join(hits))


if __name__ == "__main__":
    unittest.main(verbosity=2)
