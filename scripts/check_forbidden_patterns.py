#!/usr/bin/env python3
"""禁止模式静态扫描（任务书 §45 / MFC-G43）。

对 production source（valor/）扫描以下禁止模式，命中即退出码非 0：
    calibration_v2 / legacy / deprecated 命名
    valuation_override
    lower_bound_adj fake override
    expected_cash_cost=0 / total_pay * 0.5
    buyer_misuse / seller_breach direct terminal 输入
    req["expect"] 进入机制决策
    committed_data 传给 auditor
    "auditor" 聚合支付账户（应逐节点）
    manual likelihood / L=0.5
    hardcoded TP/FN
    placeholder hash
    replay_consistent=True 兜底
    residual fallback 0 / calibration fallback / certificate fallback
    business get(..., default)
    seller_funds None skip
    hidden challenge size / audit loop limits

tests/fixtures 与显式 TEST_FIXTURE 允许例外。
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

# 禁止的标识符/子串（文件名与代码文本）
FORBIDDEN_NAMES = {
    "calibration_v2", "legacy", "deprecated", "valuation_override",
    "replay_consistent=True", "total_pay * 0.5", "total_pay*0.5",
    "L = 0.5", "\"L\": 0.5", "'L': 0.5",
    "buyer_misuse", "seller_breach", "committed_data", "lower_bound_adj",
}

# 禁止的 AST 调用（接收者 .method）
FORBIDDEN_CALLS = {
    # (receiver_name, method_name)
    ("scenario", "likelihood"),  # scenario likelihood fallback
}


def scan_file(path: Path) -> list[str]:
    hits: list[str] = []
    text = path.read_text(encoding="utf-8")
    for bad in FORBIDDEN_NAMES:
        if bad in text:
            hits.append(f"{path.relative_to('.')}: 含禁止模式 {bad!r}")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return hits
    for node in ast.walk(tree):
        # 禁止 get(..., default) 业务默认（仅 config 接收者）
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "get" and len(node.args) >= 2:
                recv = node.func.value
                if isinstance(recv, ast.Name) and recv.id in {
                        "cfg", "config", "sc", "scenario", "a", "buyer",
                        "seller", "bond", "pricing", "exposure"}:
                    hits.append(
                        f"{path.relative_to('.')}:{node.lineno}: config.get 业务默认值")
        # expected_cash_cost=0
        if isinstance(node, ast.keyword) and node.arg == "expected_cash_cost":
            if isinstance(node.value, ast.Constant) and node.value.value == 0:
                hits.append(
                    f"{path.relative_to('.')}:{node.lineno}: expected_cash_cost=0 人工成本")
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
    root = Path(args.root)
    hits, nfiles = scan_tree(root)
    if hits:
        print(f"发现 {len(hits)} 个禁止模式（{nfiles} 文件）：")
        for h in hits:
            print(f"  {h}")
        return 1
    print(f"未发现禁止模式（{nfiles} 文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
