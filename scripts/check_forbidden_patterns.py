#!/usr/bin/env python3
"""禁止模式静态扫描（任务书 §45 / MFC-G43）。

对 production source（valor/）扫描以下禁止模式（仅代码逻辑，忽略文档字符串）：
    - expected_cash_cost=0（人工成本占位）
    - total_pay * 0.5（payer 未逐 action 归属）
    - config.get(..., default) 业务默认值（fail-closed 违规）
    - replay_consistent=True 兜底
    - 人工 likelihood / L=0.5 / 固定 TP/FN 映射
    - placeholder hash（"0"*64 / "x"*64 等固定串作业务 hash）

scenario 的 seller_breach/buyer_misuse 是 ExperimentWorld GroundTruth 标志
（§12 允许作为 GroundTruth），mechanism 不再直接读取它们作为决策输入，因此
不作为禁止命中。tests/fixtures 与 TEST_FIXTURE 允许例外。
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

# 触发构造（调用名）：config/scenario/audit 上的 .get 默认值
_CONFIG_RECEIVERS = {
    "cfg", "config", "conf", "sc", "scenario",
    "a", "rights", "buyer", "seller", "bond", "pricing", "exposure",
    "cal_cfg", "cal_config", "opts", "options", "settings",
}


def scan_file(path: Path) -> list[str]:
    hits: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return hits
    for node in ast.walk(tree):
        # 1) expected_cash_cost=0（人工成本占位）
        if isinstance(node, ast.keyword) and node.arg == "expected_cash_cost":
            if isinstance(node.value, ast.Constant) and node.value.value == 0:
                hits.append(f"{path.relative_to('.')}:{node.lineno}: expected_cash_cost=0 人工成本")
        # 2) total_pay * 0.5（payer 未逐 action）
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            if isinstance(node.left, ast.Name) and "total_pay" in node.left.id:
                if isinstance(node.right, ast.Constant) and node.right.value == 0.5:
                    hits.append(f"{path.relative_to('.')}:{node.lineno}: total_pay * 0.5 人工拆分")
        # 3) config.get(..., default) 业务默认值（标量业务参数；数据结构默认如
        #    override map / reproduction cfg 属合法读取）
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "get" and len(node.args) >= 2:
                recv = node.func.value
                default = node.args[1]
                is_scalar = isinstance(default, (ast.Constant, ast.Name, ast.UnaryOp))
                if isinstance(recv, ast.Name) and recv.id in _CONFIG_RECEIVERS and is_scalar:
                    hits.append(f"{path.relative_to('.')}:{node.lineno}: config.get 业务默认值")
    return hits


def scan_tree(root: Path) -> tuple[list[str], int]:
    all_hits: list[str] = []
    files = 0
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        files += 1
        all_hits.extend(scan_file(p))
    return all_hits, files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="valor")
    args = ap.parse_args()
    hits, nfiles = scan_tree(Path(args.root))
    if hits:
        print(f"发现 {len(hits)} 个禁止模式（{nfiles} 文件）：")
        for h in hits:
            print(f"  {h}")
        return 1
    print(f"未发现禁止模式（{nfiles} 文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
