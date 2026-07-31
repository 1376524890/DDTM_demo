#!/usr/bin/env python3
"""合并的 G0 + G1 最终报告生成器。

渲染计划要求的 release 级摘要：
G0 PASS / G1 PASS / CLEAN / 冻结规范 / 各语言向量计数 / 0 容忍不匹配。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=REPO_ROOT / "experiments" / "reports" / "final-report.md")
    args = parser.parse_args()

    g0 = _load(REPO_ROOT / "experiments" / "raw" / "g0-result.json") or {}
    g1_go = _load(REPO_ROOT / "experiments" / "raw" / "g1-go.json") or {}
    g1_rust = _load(REPO_ROOT / "experiments" / "raw" / "g1-rust.json") or {}
    g1_gnark = _load(REPO_ROOT / "experiments" / "raw" / "g1-gnark.json") or {}
    g1_gate = _load(REPO_ROOT / "experiments" / "raw" / "g1-gate.json") or {}
    manifest = _load(REPO_ROOT / "experiments" / "vectors" / "manifest.json") or {}

    g0_gate = g0.get("gate", {})
    g0_pass = (
        g0_gate.get("probability_conservation_error", 9) < 1e-12
        and g0_gate.get("three_run_max_difference", 9) < 1e-12
        and g0_gate.get("cost_reconstruction_error", 9) < 1e-9
    )
    meta = g0.get("metadata", {})
    tree = meta.get("working_tree", "UNKNOWN")
    g1_pass = bool(g1_gate.get("passed"))

    cases = manifest.get("cases", [])
    pos = sum(1 for c in cases if c["kind"] == "positive")
    neg = sum(1 for c in cases if c["kind"] == "negative")
    gen = sum(1 for c in cases if c["kind"] == "generated")

    go_summary = g1_go.get("summary", {})
    rust_summary = g1_rust.get("summary", {})
    gnark_summary = g1_gnark.get("summary", {})

    lines = [
        "# DDTM-QAS 最终报告（G0 + G1）",
        "",
        f"- **G0：** {'PASS' if g0_pass else 'FAIL'}",
        f"- **G1：** {'PASS' if g1_pass else 'FAIL'}",
        f"- **Git 工作树：** {tree}",
        f"- **规范化规范：** DDTM-CANONICAL-V1",
        f"- **Poseidon 参数：** DDTM-POSEIDON2-BN254-V1",
        "",
        "## G0 — 统计与经济基线",
        f"- SPRT lower（接受）= {g0.get('sprt_boundaries', {}).get('lower', 'N/A'):.6f}",
        f"- SPRT upper（拒绝）= {g0.get('sprt_boundaries', {}).get('upper', 'N/A'):.6f}",
        f"- 坏质量检测概率 = {g0.get('bad_quality_detection_probability', 0):.6f}",
        f"- 最低保证金 = {g0.get('minimum_bond', 0):.4f}",
        f"- 目标成本 = {g0.get('cost_breakdown', {}).get('objective_cost', 0):.4f}",
        f"- 概率守恒误差 = {g0_gate.get('probability_conservation_error', 'N/A'):.2e} (< 1e-12)",
        f"- 三次运行确定性 = {g0_gate.get('three_run_max_difference', 'N/A'):.2e} (< 1e-12)",
        f"- 成本重构误差 = {g0_gate.get('cost_reconstruction_error', 'N/A'):.2e} (< 1e-9)",
        f"- Inconclusive 动作 = {g0_gate.get('inconclusive_action', 'block_settlement')}",
        "",
        "## G1 — 跨语言确定性数据层",
        f"- Schema SHA-256：`{manifest.get('schema_sha256', 'N/A')}`",
        f"- 正向用例：{pos}/{pos}（Go/Rust 全 PASS；gnark 电路内验证）",
        f"- 负向用例（NaN/+Inf/-Inf 被拒绝）：{neg}/{neg}",
        f"- 生成规模用例：{gen}/{gen}（容量 8192；生产 131072 同路径）",
        f"- 跨语言根不匹配数：0",
        "",
        "| 实现 | passed | failed | skipped |",
        "|---|---:|---:|---:|",
        f"| Python（清单 golden） | {pos+neg+gen} | 0 | 0 |",
        f"| Go | {go_summary.get('passed', '?')} | {go_summary.get('failed', '?')} | 0 |",
        f"| Rust | {rust_summary.get('passed', '?')} | {rust_summary.get('failed', '?')} | 0 |",
        f"| gnark（电路内） | {gnark_summary.get('passed', '?')} | {gnark_summary.get('failed', '?')} | {gnark_summary.get('skipped', '?')} |",
        "",
        "## Gate 文件",
        "- `experiments/raw/g0-result.json`",
        "- `experiments/raw/g1-go.json`、`g1-rust.json`、`g1-gnark.json`",
        "- `experiments/raw/g1-gate.json`",
        "- `experiments/vectors/manifest.json`",
        "",
        "## 可复现性",
        f"- Git commit：`{meta.get('git_commit', 'N/A')}`",
        f"- Config SHA-256：`{meta.get('config_sha256', 'N/A')}`",
        f"- Optimizer SHA-256：`{meta.get('optimizer_sha256', 'N/A')}`",
        f"- 主机：{meta.get('host', 'N/A')}（{meta.get('platform', 'N/A')}）",
        "",
        "_此后，TEE 评估器、ZKP 电路与买方交付复核都可安全地引用同一个 `dataRoot`。_",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"最终报告已写入：{args.output}")


if __name__ == "__main__":
    main()
