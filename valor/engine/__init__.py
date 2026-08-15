"""VALOR Engine —— 统一交易引擎基础设施（P0 收敛层）。

把 VALOR 从"模块集合"收敛成端到端可重放系统的基础：
    RunManifest   冻结单次 run 的可复现性信息（commit/config/dataset/…/seed）
    TraceLedger   统一 hash-chain 事件账本（transaction_trace.jsonl）
    StageResult   主链阶段统一产出（下游只读上游 output）
    FormulaTrace  公式对账（论文公式 = 代码执行）
    RunArtifacts  runs/<run_id>/ 目录落盘
"""

from __future__ import annotations

from .manifest import RunManifest, default_manifest
from .trace import TraceEvent, TraceLedger
from .stage import FormulaTrace, StageResult, formula_hash
from .artifacts import RunArtifacts
from .binding import TransactionBinding, build_binding
from .scenario import CapstoneScenario
from .orchestrator import OrchestrationResult, TransactionOrchestrator, run_capstone
from .calibration import (
    AuditLikelihoodCalibrator,
    AuditPolicyCertifier,
    CalibrationBundle,
    DetectionStats,
    FrozenArtifact,
    ValuationCalibrator,
)
from .full_chain_gate import FullChainGate, evaluate_full_chain

__all__ = [
    "RunManifest",
    "default_manifest",
    "TraceEvent",
    "TraceLedger",
    "FormulaTrace",
    "StageResult",
    "formula_hash",
    "RunArtifacts",
    "TransactionBinding",
    "build_binding",
    "CapstoneScenario",
    "OrchestrationResult",
    "TransactionOrchestrator",
    "run_capstone",
    "AuditLikelihoodCalibrator",
    "AuditPolicyCertifier",
    "CalibrationBundle",
    "DetectionStats",
    "FrozenArtifact",
    "ValuationCalibrator",
    "FullChainGate",
    "evaluate_full_chain",
]
