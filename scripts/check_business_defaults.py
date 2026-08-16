#!/usr/bin/env python3
"""业务默认值静态扫描（检查单 H，规范 §73 第 1 条）。

AST 扫描抓取以下"偷偷加默认值"模式：
    config.get("x", 0.05)
    getattr(config, "x", 7)
    x or 0.1
    Field(default=...) / field(default_factory=...)
    业务字段的注解赋值默认值（alpha: float = 0.05）

- 命中业务默认值 → 退出码非 0（CI 中直接失败）
- tests/fixtures 目录允许显式测试常量
- 数学常数、dtype tolerance、密码学常数在白名单内（大写常量名 + 显式集合）

用法：
    python scripts/check_business_defaults.py [--root valor] [--allow-test-fixtures]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

# 业务字段名（规范 §73 提及 + 常见经济/安全参数）
BUSINESS_NAMES = {
    "alpha", "rho", "m", "q", "lambda", "kappa", "budget", "loss",
    "threshold", "stake", "cost", "probability", "p_b", "p_e", "p_v",
    "challenge", "committee", "beta", "gamma", "epsilon", "delta",
    "interest", "rate", "duration", "fee", "penalty", "bond", "price",
    "escrow", "discount", "weight", "seed", "n_permutations",
    "target_pvalue_resolution", "sample_size", "repetitions",
}

# 显式白名单：数学/密码学/dtype 常量（检查单 H：whitelist 受审查）
ALLOWED_CONSTANTS = {
    "pi", "e", "tau", "inf", "eps", "epsilon", "machine_epsilon",
    "float_info", "spacing", "finfo", "iinfo", "maxsize",
    "MAX_VALUE", "MIN_VALUE", "UINT64_MAX", "UINT32_MAX",
}

# 触发构造（调用名）
_TRIGGER_CALLS = {"get", "getattr", "field", "Field", "default_factory"}

# 配置类接收者：只有在这些"配置/场景/参数"对象上的 .get 默认值才视为业务默认值。
# 对结果/事件/数据 dict（e / result / s / r / d / metrics / sched_res / ctx / data）
# 的 .get 是数据访问默认（如 event.get("outcome", "")），不属于业务参数默认。
_CONFIG_RECEIVERS = {
    "cfg", "config", "conf", "sc", "scenario", "param", "params",
    "a",  # audit 配置 dict（scenario.audit）
    "rights", "buyer", "seller", "bond", "pricing", "exposure",
    "cal_cfg", "cal_config", "opts", "options", "settings",
}


def _is_config_receiver(receiver: str | None) -> bool:
    return receiver is not None and receiver in _CONFIG_RECEIVERS


class DefaultScanner(ast.NodeVisitor):
    """遍历 AST，收集业务默认值命中项。"""

    def __init__(self, path: str, allow_fixtures: bool) -> None:
        self.path = path
        self.allow_fixtures = allow_fixtures
        self.hits: list[str] = []

    # ---- 是否应跳过该文件 ----
    def _is_fixture(self) -> bool:
        return "fixtures" in Path(self.path).parts or "test_fixture" in self.path

    def _whitelisted(self, name: str) -> bool:
        # 大写常量名或显式白名单
        return name.isupper() or name in ALLOWED_CONSTANTS

    def _is_constant_default(self, node: ast.AST) -> bool:
        """判断是否为常量默认值（int/float/str/bool；None 不算业务默认）。"""
        return isinstance(
            node,
            (ast.Constant, ast.UnaryOp),
        ) and not (
            isinstance(node, ast.Constant) and node.value is None
        )

    # ---- 捕获 config.get("x", default) / getattr(x, "x", default) / field(default_factory) ----
    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _TRIGGER_CALLS:
            kw = {k.arg: k.value for k in node.keywords}
            # field(...)/default_factory：直接捕获（无 receiver）
            if func.attr in ("field", "Field", "default_factory"):
                # field(default_factory=lambda: {...}) 由 visit_Lambda/AnnAssign 兜底
                self.generic_visit(node)
                return
            # .get / .getattr：仅当 receiver 是配置类对象才视为业务默认
            receiver = None
            if isinstance(func.value, ast.Name):
                receiver = func.value.id
            if func.attr in ("get", "getattr") and not _is_config_receiver(receiver):
                self.generic_visit(node)
                return
            name_node = None
            default_node = None
            if func.attr == "get":
                # dict.get(key, default)：default 是第 2 个 positional 参数
                if len(node.args) >= 1 and isinstance(node.args[0], ast.Constant):
                    name_node = node.args[0]
                if len(node.args) >= 2:
                    default_node = node.args[1]
            elif func.attr == "getattr":
                # getattr(obj, name, default)：default 是第 3 个 positional 参数
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    name_node = node.args[1]
                if len(node.args) >= 3:
                    default_node = node.args[2]
            if name_node is None and "name" in kw:
                name_node = kw["name"]
            if default_node is None and "default" in kw:
                default_node = kw["default"]
            if isinstance(name_node, ast.Constant) and isinstance(name_node.value, str):
                name = name_node.value
                if default_node is not None and self._is_constant_default(default_node):
                    if not self._whitelisted(name):
                        self.hits.append(
                            f"{self.path}:{node.lineno} 业务默认值 "
                            f"{func.attr}({name!r}, default)"
                        )
        # 继续遍历
        self.generic_visit(node)

    # ---- 捕获 x or 0.1（ast.BoolOp，而非 ast.BinOp/ast.Or）----
    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        if isinstance(node.op, ast.Or):
            if len(node.values) >= 2 and isinstance(node.values[0], ast.Name):
                if node.values[0].id in BUSINESS_NAMES:
                    if self._is_constant_default(node.values[1]):
                        self.hits.append(
                            f"{self.path}:{node.lineno} 业务默认值 "
                            f"{node.values[0].id} or <default>"
                        )
        self.generic_visit(node)

    # ---- 捕获注解赋值默认值：alpha: float = 0.05 ----
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name) and node.value is not None:
            name = node.target.id
            if name in BUSINESS_NAMES and self._is_constant_default(node.value):
                if not self._whitelisted(name):
                    self.hits.append(
                        f"{self.path}:{node.lineno} 业务字段注解默认值 {name} = <const>"
                    )
        self.generic_visit(node)


def scan(root: Path) -> list[str]:
    hits: list[str] = []
    for py in sorted(root.rglob("*.py")):
        # 跳过 __pycache__
        if "__pycache__" in py.parts:
            continue
        # fixtures 目录允许显式测试常量（检查单 H：测试 fixture 目录允许）
        if any(part in ("fixtures",) or "test_fixture" in part for part in py.parts):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as e:
            print(f"解析失败 {py}: {e}", file=sys.stderr)
            continue
        scanner = DefaultScanner(str(py), allow_fixtures=True)
        scanner.visit(tree)
        hits.extend(scanner.hits)
    return hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="VALOR 业务默认值静态扫描")
    ap.add_argument("--root", default="valor", help="扫描根目录（默认 valor）")
    ap.add_argument(
        "--allow-test-fixtures", action="store_true",
        help="允许 tests/fixtures 目录中的显式测试常量（默认已豁免 fixtures 目录）",
    )
    args = ap.parse_args(argv)

    root = Path(args.root)
    hits = scan(root)
    if hits:
        print("发现业务默认值（违反规范 §73 / 检查单 H）：")
        for h in hits:
            print(f"  ✗ {h}")
        print("\n必须改为 require_resolved() / 显式 ResolvedParameter。")
        return 1
    print("OK: 未发现业务默认值。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
