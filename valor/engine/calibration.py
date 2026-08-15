"""离线校准与认证（P6）—— 冻结在线交易引用的 artifact。

对齐交接文档第六/十节：
- 正式交易禁止 `valuation_override` 或 `estimated_value × 0.8`；
  必须先离线跑伪历史交易，形成独立 calibration residual：
      e_i = V_i^real - V̂_i^gross，Q_{α_V}(e)
  V̲_gross = V̂_gross + Q_{α_V}(e)。
- 检测认证必须"在线交易之前冻结"：Calibration → freeze Π_A → 受控 breach
  injection → independent certification runs → TP/FN → Beta posterior →
  lower bound → Certificate。在线交易只做 certificate lookup。
- 似然 Λ_j 由实际检测敏感度/误报派生，不用 config 手填。

产出三类冻结 artifact：
    ValuationCalibrationArtifact（residual → V̲ 下界）
    AuditLikelihoodArtifact（Λ_j 由检测 TP/FP 派生）
    AuditPolicyCertificate（policy_hash / TP / FN / Beta / p̲_B^sys / envelope）
每个 artifact 带确定性 hash，在线交易 manifest 引用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from valor.core.hashing import content_hash
from valor.security.certification import CertifiedCell, CertificationCatalog


# ---------------------------------------------------------------------------
# Artifact 基类与冻结
# ---------------------------------------------------------------------------
@dataclass
class FrozenArtifact:
    """冻结 artifact：内容 + 确定性 hash。"""

    kind: str
    data: dict[str, Any]

    @property
    def artifact_hash(self) -> str:
        return content_hash({"kind": self.kind, "data": self.data})

    def to_plain(self) -> dict:
        return {"kind": self.kind, "data": self.data, "artifact_hash": self.artifact_hash}


# ---------------------------------------------------------------------------
# 1. 估值校准（Valuation Calibration）
# ---------------------------------------------------------------------------
class ValuationCalibrator:
    """维护独立 pseudo-historical residual，输出 V̲ 下界（§28）。"""

    def __init__(self, alpha_v: float) -> None:
        self.alpha_v = alpha_v
        self._residuals: list[float] = []

    def add(self, realized: float, predicted: float) -> None:
        self._residuals.append(realized - predicted)

    @property
    def n_samples(self) -> int:
        return len(self._residuals)

    def lower_bound_adjustment(self) -> float:
        """Q_{α_V}(Ê)：保守下界增量。"""
        if not self._residuals:
            raise ValueError("估值校准器无样本，无法给出下界（禁止隐式 0）")
        return float(np.quantile(self._residuals, self.alpha_v))

    def coverage(self) -> float:
        """Coverage_V = P(V^real ≥ V̲)。"""
        if not self._residuals:
            return 0.0
        adj = self.lower_bound_adjustment()
        return float(np.mean([r >= adj for r in self._residuals]))

    def freeze(self, *, dataset_hash: str, trainer_hash: str,
               buyer_context_family: str, seed: int) -> FrozenArtifact:
        if not self._residuals:
            raise ValueError("估值校准冻结失败：无样本")
        return FrozenArtifact(kind="valuation_calibration", data={
            "alpha_v": self.alpha_v,
            "n_samples": self.n_samples,
            "residual_quantile": self.lower_bound_adjustment(),
            "coverage": self.coverage(),
            "residuals": self._residuals,
            "dataset_hash": dataset_hash,
            "trainer_hash": trainer_hash,
            "buyer_context_family": buyer_context_family,
            "seed": seed,
        })


# ---------------------------------------------------------------------------
# 2. 审计似然校准（Audit Likelihood）—— 由检测敏感度/误报派生 Λ_j
# ---------------------------------------------------------------------------
@dataclass
class DetectionStats:
    """一次受控 breach injection 的检测统计（TP/FP/FN/TN）。"""

    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def sensitivity(self) -> float:
        """TPR = TP/(TP+FN)。"""
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def false_positive_rate(self) -> float:
        """FPR = FP/(FP+TN)。"""
        return self.fp / (self.fp + self.tn) if (self.fp + self.tn) else 0.0

    def to_plain(self) -> dict:
        return {"tp": self.tp, "fp": self.fp, "fn": self.fn, "tn": self.tn}


class AuditLikelihoodCalibrator:
    """由检测统计派生 Λ_j(y, x)，不手填似然。"""

    def __init__(self, *, action_id: str, breach_family: str,
                 prior_state_probs: dict[str, float]) -> None:
        self.action_id = action_id
        self.breach_family = breach_family
        self.prior_state_probs = prior_state_probs  # {G,L,B}

    def likelihood_rows(self, det: DetectionStats) -> dict[str, dict[str, float]]:
        """Λ_j(y, x) 由 sensitivity/FPR 派生。

        三态 x∈{G,L,B}；观测 y∈{PASS, QUALITY_FAIL, BREACH_EVIDENCE}。
        检测对 G/L 无区分（不触发 breach），对 B 触发 BREACH_EVIDENCE。
        """
        tpr = det.sensitivity
        fpr = det.false_positive_rate
        # 对 Good/Latent：P(BREACH_EVIDENCE)=FPR；P(PASS)=1-FPR
        # 对 Breach：P(BREACH_EVIDENCE)=TPR；P(PASS)=1-TPR
        # 三行必须全部非零（bayes_update 需 Σ Λ_j(y,x) π_x > 0 对任意 y）。
        # QUALITY_FAIL：表示 latent 质量问题的中等强度观测（区分 L 与 G/B）。
        rows = {
            "PASS": {
                "G": 1.0 - fpr, "L": 1.0 - fpr, "B": 1.0 - tpr,
            },
            "QUALITY_FAIL": {
                "G": fpr, "L": 0.5, "B": fpr,
            },
            "BREACH_EVIDENCE": {
                "G": fpr, "L": 0.5, "B": tpr,
            },
        }
        return rows

    def freeze(self, *, det: DetectionStats, policy_hash: str) -> FrozenArtifact:
        return FrozenArtifact(kind="audit_likelihood", data={
            "action_id": self.action_id,
            "breach_family": self.breach_family,
            "detection_stats": det.to_plain(),
            "sensitivity": det.sensitivity,
            "false_positive_rate": det.false_positive_rate,
            "rows": self.likelihood_rows(det),
            "policy_hash": policy_hash,
        })


# ---------------------------------------------------------------------------
# 3. 审计策略证书（Audit Policy Certificate）
# ---------------------------------------------------------------------------
class AuditPolicyCertifier:
    """由独立 certification runs 的 TP/FN 计算 p̲_B^sys，冻结证书。"""

    def __init__(self, *, a_D: float, b_D: float, alpha_D: float) -> None:
        self.a_D = a_D
        self.b_D = b_D
        self.alpha_D = alpha_D

    def certify(self, *, cell_id: str, breach_family: str, tp: int, fn: int,
                policy_hash: str, action_catalog_hash: str) -> FrozenArtifact:
        """用实际 TP/FN 计算 Beta 下界，冻结证书。"""
        cat = CertificationCatalog()
        cat.register(CertifiedCell(
            cell_id, self.a_D, self.b_D, self.alpha_D,
            {breach_family: (tp, fn)}))
        p_b_lower = cat.p_breach_lower(cell_id, breach_family)
        return FrozenArtifact(kind="audit_policy_certificate", data={
            "policy_hash": policy_hash,
            "action_catalog_hash": action_catalog_hash,
            "cell_id": cell_id,
            "breach_family": breach_family,
            "a_D": self.a_D, "b_D": self.b_D, "alpha_D": self.alpha_D,
            "tp": tp, "fn": fn,
            "p_breach_lower_sys": p_b_lower,
        })

    @classmethod
    def from_frozen(cls, art: FrozenArtifact) -> "AuditPolicyCertifier":
        d = art.data
        return cls(a_D=d["a_D"], b_D=d["b_D"], alpha_D=d["alpha_D"])


# ---------------------------------------------------------------------------
# 4. 运行器：一次完整离线校准
# ---------------------------------------------------------------------------
@dataclass
class CalibrationBundle:
    """一次离线校准的全部冻结 artifact。"""

    valuation: FrozenArtifact | None
    likelihood: FrozenArtifact | None
    certificate: FrozenArtifact | None

    def to_plain(self) -> dict:
        return {
            "valuation": self.valuation.to_plain() if self.valuation else None,
            "likelihood": self.likelihood.to_plain() if self.likelihood else None,
            "certificate": self.certificate.to_plain() if self.certificate else None,
        }

    def hashes(self) -> dict[str, str]:
        return {
            "valuation_calibration_hash": self.valuation.artifact_hash if self.valuation else "",
            "likelihood_hash": self.likelihood.artifact_hash if self.likelihood else "",
            "certificate_hash": self.certificate.artifact_hash if self.certificate else "",
        }


__all__ = [
    "FrozenArtifact",
    "ValuationCalibrator",
    "DetectionStats",
    "AuditLikelihoodCalibrator",
    "AuditPolicyCertifier",
    "CalibrationBundle",
]
