"""`python -m valor experiment run --config` 的唯一实验入口。

统一走 valor/experiments/ 框架（spec/registry/pairing/runner/analysis），
任何 trial 都经过 TransactionOrchestrator，只允许一套实验框架。
"""

from __future__ import annotations

import json
from pathlib import Path


def run_experiment_cli(config_path: str) -> int:
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    exp = cfg.get("experiment", {})
    mode = exp.get("mode", "sweep")

    if mode == "sweep":
        return _run_sweep(cfg, exp)
    if mode == "paired":
        return _run_paired(cfg, exp)
    raise ValueError(f"未知实验 mode: {mode!r}（只支持 sweep / paired）")


def _run_sweep(cfg: dict, exp: dict) -> int:
    """参数扫描：同一场景上扫一个参数，每次经过 orchestrator。"""
    import csv
    import os

    from valor.engine.scenario import scenario_from_config

    param = exp["sweep_param"]
    values = exp["values"]
    out_dir = exp.get("out_dir", "raw/experiments")
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for value in values:
        variant = json.loads(json.dumps(cfg))
        _set_nested(variant, param, value)
        sc = scenario_from_config(variant)
        from valor.engine import TransactionOrchestrator

        try:
            orch = TransactionOrchestrator(sc, run_dir=out_dir)
            res = orch.run()
            pricing = orch._stages.get("pricing")
            pr = pricing.output if pricing else {}
            rows.append({
                param: value,
                "decision": res.decision,
                "p_max": pr.get("p_max"),
                "p_min": pr.get("p_min"),
                "margin": pr.get("margin"),
            })
        except Exception as e:  # noqa: BLE001
            rows.append({param: value, "decision": "ERROR", "error": str(e)})
    with open(os.path.join(out_dir, "summary.csv"), "w", newline="",
              encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"实验完成：{len(rows)} 次运行，输出到 {out_dir}")
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def _run_paired(cfg: dict, exp: dict) -> int:
    """paired 实验：走 valor/experiments/ 完整框架。"""
    from .cli_paired import run_paired_cli

    return run_paired_cli(cfg, exp)


def _set_nested(cfg: dict, path: str, value) -> None:
    keys = path.split(".")
    node = cfg
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value


__all__ = ["run_experiment_cli"]
