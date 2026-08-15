"""StageResult / FormulaTrace —— 阶段结果与公式对账（P0 基础设施）。

StageResult 是每个主链阶段的统一产出：下游只能读取上游 StageResult 的
output，禁止从 config 重填同一个量。

FormulaTrace 用于「公式对账」（Level 1 Mathematical Reconciliation）：
记录 formula_id、inputs、computed output，以及独立重算 recomputed；
reconcile() 断言 computed 与 recomputed 在容差内一致（论文公式=代码执行）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import hash_object


@dataclass
class StageResult:
    """一个主链阶段的统一结果。

    stage: 阶段名（如 "DATA_VOI"）
    output: 本阶段的数值产出（下游只读这个）
    evidence_refs: 本阶段引用的上游证据/事件（seq 列表或 artifact 引用）
    status: PASS / FAIL / SKIP
    notes: 可读说明
    """

    stage: str
    output: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    status: str = "PASS"
    notes: str = ""

    def to_plain(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "output": self.output,
            "evidence_refs": self.evidence_refs,
            "status": self.status,
            "notes": self.notes,
        }

    @classmethod
    def from_plain(cls, d: dict[str, Any]) -> "StageResult":
        return cls(
            stage=d["stage"], output=d.get("output", {}),
            evidence_refs=d.get("evidence_refs", []),
            status=d.get("status", "PASS"), notes=d.get("notes", ""),
        )

    # 下游只读 output 的便捷取值（禁止 config 重填）
    def get(self, key: str, default: Any = None) -> Any:
        return self.output.get(key, default)


@dataclass
class FormulaTrace:
    """一条公式对账记录。

    inputs: 计算输入（必须可 canonicalize）
    computed: 代码实际计算值
    recompute(): 独立重算函数，返回 (value, tolerance) 或抛出
    formula_id: 公式标识（如 "DATA_VOI_MARGINAL"）
    """

    formula_id: str
    inputs: dict[str, Any]
    computed: Any
    stage: str = ""
    recompute_fn=None  # callable(inputs) -> (value, tolerance)
    recomputed: Any = None
    tolerance: float | None = None
    passed: bool | None = None

    def reconcile(self) -> "FormulaTrace":
        """独立重算并对账；结果写入 self。"""
        if self.recompute_fn is None:
            self.passed = None
            return self
        value, tol = self.recompute_fn(self.inputs)
        self.recomputed = value
        self.tolerance = tol
        self.passed = abs(float(self.computed) - float(value)) <= float(tol)
        return self

    def to_plain(self) -> dict[str, Any]:
        return {
            "formula_id": self.formula_id,
            "stage": self.stage,
            "inputs": self.inputs,
            "computed": self.computed,
            "recomputed": self.recomputed,
            "tolerance": self.tolerance,
            "passed": self.passed,
        }

    @classmethod
    def from_plain(cls, d: dict[str, Any]) -> "FormulaTrace":
        return cls(
            formula_id=d["formula_id"], inputs=d.get("inputs", {}),
            computed=d.get("computed"), stage=d.get("stage", ""),
            recomputed=d.get("recomputed"), tolerance=d.get("tolerance"),
            passed=d.get("passed"),
        )


def formula_hash(ft: FormulaTrace) -> str:
    """公式对账记录的内容哈希（可复算）。"""
    return hash_object(ft.to_plain())


__all__ = ["StageResult", "FormulaTrace", "formula_hash"]
