#!/usr/bin/env python3
"""Mechanism purity scanner for Round 7 adversarial closure.

Flags experiment/fault/ground-truth shortcuts and legacy bool shortcuts inside
mechanism packages except in explicit experiment adapters and world builders.
The scanner only looks at executable code (not docstrings/comments) and only
flags decision-path shortcut identifiers, not legitimate world labels such as
`ground_truth_ref`.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

FORBIDDEN_NAMES = {
    "ground_truth_seller_breach",
    "delivery_hash_mismatch",
    "offline_nodes",
    "invalid_signature_nodes",
    "expected_answer",
    "replay_consistent",
    "final_eval_accessed_before_decision",
}
# Allowed to appear in these files/dirs (experiment world builders and adapters)
ALLOWED_DIRS = {"experiments", "adapters", "tests", "fixtures"}
ALLOWED_FILES = {"experiment_world.py", "adapters.py"}


def is_allowed(path: Path) -> bool:
    for part in path.parts:
        if part in ALLOWED_DIRS:
            return True
    if path.name in ALLOWED_FILES:
        return True
    return False


def scan_file(path: Path) -> list[str]:
    hits: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return hits
    for node in ast.walk(tree):
        # skip docstrings/comments naturally: only Name/Attribute nodes
        if isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                hits.append(f"{path.relative_to('.')}:{node.lineno}: forbidden name {node.id}")
        elif isinstance(node, ast.Attribute):
            attr = node.attr
            if attr in FORBIDDEN_NAMES:
                hits.append(f"{path.relative_to('.')}:{node.lineno}: forbidden attr {attr}")
            if isinstance(node.value, ast.Name) and node.value.id == "scenario" and attr in ("likelihood", "certificate"):
                hits.append(f"{path.relative_to('.')}:{node.lineno}: scenario.{attr} fallback")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="valor")
    args = ap.parse_args()
    root = Path(args.root)
    hits: list[str] = []
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        if is_allowed(p):
            continue
        hits.extend(scan_file(p))
    # dedupe preserving order
    seen = set()
    uniq = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            uniq.append(h)
    if uniq:
        print(f"发现 {len(uniq)} 个机制纯度违规：")
        for h in uniq:
            print(f"  {h}")
        return 1
    print("未发现机制纯度违规")
    return 0


if __name__ == "__main__":
    sys.exit(main())
