"""G0 报告生成器与 CLI 入口。

运行完整的 G0 流水线——在评估网格和两个边界处做 SPRT 评估、JABO 保证金与成本、
收敛 gate、三次运行确定性、release 元数据——并写出结构化 JSON 结果与人类可读的
Markdown 报告。

用法::

    python -m experiments.g0.report --config experiments/configs/g0-default.json --release
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .convergence import (
    check_cost_reconstruction,
    check_inconclusive_not_settled,
    check_probability_conservation,
    check_three_run_determinism,
)
from .config import load_config
from .jabo import minimum_bond, objective_cost
from .metadata import collect_metadata
from .models import CostBreakdown, ExperimentConfig, OperatingPoint, to_plain
from .sprt import evaluate_operating_point, sprt_constants

REPO_ROOT = Path(__file__).resolve().parents[2]


class Evaluation:
    """持有供 gate 使用的 dataclass 对象，以及供 JSON 使用的纯字典视图。"""

    def __init__(self, config: ExperimentConfig) -> None:
        self.points = [
            evaluate_operating_point(c, config.sprt)
            for c in config.evaluation_grid
        ]
        self.at_good = evaluate_operating_point(config.sprt.tau_good, config.sprt)
        self.at_bad = evaluate_operating_point(config.sprt.tau_bad, config.sprt)

        detection = self.at_bad.reject_probability
        self.bond = minimum_bond(detection, config.economics)
        self.cost = objective_cost(
            self.at_good, self.at_bad, self.bond, config.economics
        )
        self.lower, self.upper, _hit, _clean = sprt_constants(config.sprt)
        self.detection = detection

    def to_dict(self) -> dict:
        return {
            "sprt_boundaries": {"lower": self.lower, "upper": self.upper},
            "bad_quality_detection_probability": self.detection,
            "minimum_bond": self.bond,
            "cost_breakdown": asdict(self.cost),
            "operating_points": [asdict(p) for p in self.points],
            "boundary_points": {
                "tau_good": asdict(self.at_good),
                "tau_bad": asdict(self.at_bad),
            },
        }


def run(config: ExperimentConfig, release: bool) -> dict:
    """评估、跑 gate、证明确定性、收集元数据。"""
    evaluation = Evaluation(config)

    # --- Gate 检查（违反即抛错）---
    max_pc = check_probability_conservation(evaluation.points)
    cost_err = check_cost_reconstruction(evaluation.cost)
    check_inconclusive_not_settled(evaluation.at_bad)

    # --- 结构化结果上的三次运行确定性 ---
    runs = [Evaluation(config).to_dict() for _ in range(3)]
    determinism = check_three_run_determinism(runs)

    # --- release 元数据 ---
    config_path = REPO_ROOT / "experiments" / "configs" / "g0-default.json"
    optimizer_path = Path(__file__).resolve().parent / "sprt.py"
    dataset_path = REPO_ROOT / "data" / "raw" / "synthetic.npz"
    metadata = collect_metadata(
        repository=REPO_ROOT,
        config_path=config_path,
        optimizer_path=optimizer_path,
        dataset_path=dataset_path if dataset_path.exists() else None,
        release_mode=release,
    )

    result = evaluation.to_dict()
    result["gate"] = {
        "probability_conservation_error": max_pc,
        "cost_reconstruction_error": cost_err,
        "three_run_max_difference": determinism,
        "inconclusive_action": config.inconclusive_action.value,
    }
    result["metadata"] = metadata
    result["config"] = to_plain(config)
    return result


def render_markdown(result: dict, config: ExperimentConfig) -> str:
    """把结构化结果渲染为 G0 的 Markdown 报告。"""
    b = result["cost_breakdown"]
    meta = result["metadata"]
    gate = result["gate"]
    lines = [
        "# G0 报告 — 统计与经济基线",
        "",
        f"- **Git commit：** `{meta['git_commit']}`",
        f"- **工作树：** {meta['working_tree']}",
        f"- **Config SHA-256：** `{meta['config_sha256']}`",
        f"- **Optimizer SHA-256：** `{meta['optimizer_sha256']}`",
        f"- **Dataset SHA-256：** `{meta['dataset_sha256'] or 'N/A'}`",
        "",
        "## SPRT 边界",
        f"- lower（接受）= {result['sprt_boundaries']['lower']:.6f}",
        f"- upper（拒绝）= {result['sprt_boundaries']['upper']:.6f}",
        "",
        "## JABO 经济",
        f"- 坏质量检测概率 = {result['bad_quality_detection_probability']:.6f}",
        f"- 最低保证金 = {result['minimum_bond']:.6f}",
        f"- 目标成本 = {b['objective_cost']:.6f}",
        "",
        "> 审计成本在 epsilon = tau_good 处评估",
        "> 残差损失在 epsilon = tau_bad 处评估",
        f"> Inconclusive 动作 = {gate['inconclusive_action']}",
        "",
        "| 分量 | 数值 |",
        "|---|---:|",
        f"| row_audit_cost | {b['row_audit_cost']:.6f} |",
        f"| proof_batch_cost | {b['proof_batch_cost']:.6f} |",
        f"| audit_cost | {b['audit_cost']:.6f} |",
        f"| bond_capital_cost | {b['bond_capital_cost']:.6f} |",
        f"| residual_loss | {b['residual_loss']:.6f} |",
        f"| **objective_cost** | **{b['objective_cost']:.6f}** |",
        "",
        "## Operating points",
        "| contamination | P(accept) | P(reject) | P(inconc) | E[T] | E[ceil(T/64)] |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for p in result["operating_points"]:
        lines.append(
            f"| {p['contamination']} | {p['accept_probability']:.6e} | "
            f"{p['reject_probability']:.6e} | {p['inconclusive_probability']:.6e} | "
            f"{p['expected_samples']:.4f} | {p['expected_batches']:.4f} |"
        )
    lines += [
        "",
        "## Gate",
        "| 检查 | 判据 | 结果 | 状态 |",
        "|---|---|---:|---|",
        f"| 概率守恒 | max|P+R+I-1| < 1e-12 | {gate['probability_conservation_error']:.2e} | {'PASS' if gate['probability_conservation_error'] < 1e-12 else 'FAIL'} |",
        f"| 三次运行确定性 | max_diff < 1e-12 | {gate['three_run_max_difference']:.2e} | {'PASS' if gate['three_run_max_difference'] < 1e-12 else 'FAIL'} |",
        f"| 成本重构 | |J-sum(parts)| < 1e-9 | {gate['cost_reconstruction_error']:.2e} | {'PASS' if gate['cost_reconstruction_error'] < 1e-9 else 'FAIL'} |",
        f"| 工作树（release） | CLEAN | {meta['working_tree']} | {'PASS' if meta['working_tree'] == 'CLEAN' else 'FAIL'} |",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="G0 统计/经济报告")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--release", action="store_true", help="要求 CLEAN 工作树")
    parser.add_argument("--output", type=Path, help="结构化 JSON 输出路径")
    parser.add_argument("--report", type=Path, help="Markdown 报告输出路径")
    args = parser.parse_args()

    config = load_config(args.config)
    result = run(config, release=args.release)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    report_md = render_markdown(result, config)
    report_path = args.report or (
        REPO_ROOT / "experiments" / "reports" / "g0-report.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_md, encoding="utf-8")

    print(report_md)
    print(f"\nG0 markdown 报告：{report_path}")
    if args.output:
        print(f"G0 结构化 JSON：{args.output}")


if __name__ == "__main__":
    main()
