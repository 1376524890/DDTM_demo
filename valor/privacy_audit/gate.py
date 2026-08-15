"""PP-AUDIT-G01..G12 隐私审计验收 Gate。

全部通过才允许 Privacy Audit Integration = PASS。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class PrivacyAuditGateResult:
    passed: bool
    checks: dict[str, bool]
    failures: list[str]

    def to_plain(self) -> dict:
        return {
            "privacy_audit_integration": "PASS" if self.passed else "FAIL",
            "checks": self.checks,
            "failures": self.failures,
        }


class PrivacyAuditGate:
    """PP-AUDIT-G01..G12 验收。"""

    def __init__(self, context: dict[str, Any]) -> None:
        """context 提供验收所需的对象（见各 check 注释）。"""
        self.ctx = context

    def _check(self, results: dict[str, bool], name: str, fn) -> None:
        try:
            results[name] = bool(fn())
        except Exception:
            results[name] = False

    def run(self) -> PrivacyAuditGateResult:
        results: dict[str, bool] = {}
        ctx = self.ctx

        # G01 auditor 文件系统无全量数据
        self._check(results, "PP-AUDIT-G01",
                    lambda: ctx.get("auditor_has_no_full_data", False))
        # G02 交易承诺先于挑战（commitment 时间 < challenge 时间）
        self._check(results, "PP-AUDIT-G02",
                    lambda: ctx.get("commitment_before_challenge", False))
        # G03 挑战不可预测（challenge nonce 随机 / commitment 后才生成）
        self._check(results, "PP-AUDIT-G03",
                    lambda: ctx.get("challenge_unpredictable", False))
        # G04 所有揭示行通过 Merkle 根验证
        self._check(results, "PP-AUDIT-G04",
                    lambda: ctx.get("all_openings_verify", False))
        # G05-G08 篡改检测（pixel/label/index/merkle path）
        self._check(results, "PP-AUDIT-G05",
                    lambda: ctx.get("tamper_pixel_detected", False))
        self._check(results, "PP-AUDIT-G06",
                    lambda: ctx.get("tamper_label_detected", False))
        self._check(results, "PP-AUDIT-G07",
                    lambda: ctx.get("tamper_index_detected", False))
        self._check(results, "PP-AUDIT-G08",
                    lambda: ctx.get("tamper_merkle_detected", False))
        # G09 隐私预算永不被超过
        self._check(results, "PP-AUDIT-G09",
                    lambda: ctx.get("privacy_budget_never_exceeded", False))
        # G10 审计 likelihood 来自校准 artifact
        self._check(results, "PP-AUDIT-G10",
                    lambda: ctx.get("likelihood_from_calibration", False))
        # G11 实际 VCG 支付进入 Audit-VOI
        self._check(results, "PP-AUDIT-G11",
                    lambda: ctx.get("vcg_in_audit_voi", False))
        # G12 所有 evidence/commitment/challenge hash 已归档
        self._check(results, "PP-AUDIT-G12",
                    lambda: ctx.get("hashes_archived", False))

        failures = [k for k, v in results.items() if not v]
        return PrivacyAuditGateResult(
            passed=not failures, checks=results, failures=failures)


def run_privacy_audit_gate(context: dict[str, Any]) -> dict:
    return PrivacyAuditGate(context).run().to_plain()


__all__ = ["PrivacyAuditGate", "PrivacyAuditGateResult", "run_privacy_audit_gate"]
