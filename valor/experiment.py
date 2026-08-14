"""实验运行（Phase 8 / 规范 §66）。

对指定参数扫描，运行全流程交易，收集成交决策，输出 raw JSON + summary CSV。
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from .run import run_full_transaction


def _set_nested(cfg: dict, path: str, value) -> None:
    keys = path.split(".")
    node = cfg
    for k in keys[:-1]:
        node = node[k]
    node[keys[-1]] = value


def run_experiments(config_path: str) -> int:
    """扫描参数运行实验。"""
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    exp = cfg.get("experiment", {})
    param = exp["sweep_param"]
    values = exp["values"]
    out_dir = exp.get("out_dir", "raw/experiments")
    os.makedirs(out_dir, exist_ok=True)

    rows = []
    for value in values:
        variant = json.loads(json.dumps(cfg))  # 深拷贝
        _set_nested(variant, param, value)
        try:
            result = run_full_transaction(variant)
            decision = result.get("decision", "NO_TRADE")
            pricing = result.get("pricing", {})
            rows.append({
                param: value,
                "decision": decision,
                "p_max": pricing.get("p_max"),
                "p_min": pricing.get("p_min"),
                "margin": pricing.get("margin"),
            })
        except Exception as e:  # noqa: BLE001
            rows.append({param: value, "decision": "ERROR", "error": str(e)})

    summary_path = os.path.join(out_dir, "summary.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"实验完成：{len(rows)} 次运行，输出到 {out_dir}")
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0
