"""AuditExecutionContext + CommitChallengeVerifier（PPA-4 核心）。

节点侧执行 COMMIT_CHALLENGE：
    1. verify_task_binding(task, ctx)
    2. 对每个 opening：verify_opening → 任一失败 = BREACH_EVIDENCE
    3. decode openings → 只保留 k 行在内存
    4. run_primitive(claim) → metrics
    5. 构造 PrivacyAuditEvidence

auditor 内存永远只有 k 行，不持有全量数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .commitment import DatasetCommitment
from .claims import AggregateClaim
from .challenge import RowChallenge
from .evidence import PrivacyAuditEvidence, build_evidence
from .models import AuditExecutionMode, PrimitiveResult
from .opening import RowOpening, verify_opening
from .primitives import run_primitive


@dataclass
class AuditExecutionContext:
    """节点审计执行上下文（方案 §19）。"""

    commitment: DatasetCommitment
    claim: AggregateClaim
    challenge: RowChallenge | None = None
    openings: list[RowOpening] = field(default_factory=list)
    full_data: Any | None = None  # 仅 FULL_DATA 模式

    def to_plain(self) -> dict:
        return {
            "commitment": self.commitment.to_plain(),
            "claim": self.claim.to_plain(),
            "challenge": self.challenge.to_plain() if self.challenge else None,
            "n_openings": len(self.openings),
            "has_full_data": self.full_data is not None,
        }


class CommitChallengeVerifier:
    """COMMIT_CHALLENGE 模式节点侧验证器。"""

    def verify_task_binding(self, task_binding_hash: str, ctx: AuditExecutionContext) -> bool:
        """校验任务承诺与 commitment/claim 绑定。"""
        return (
            ctx.challenge is not None
            and ctx.challenge.task_binding_hash == task_binding_hash
            and len(ctx.openings) > 0
            and len(ctx.openings) == len(ctx.challenge.indices)
        )

    def verify_all_openings(self, ctx: AuditExecutionContext) -> bool:
        """所有 opening 必须通过 Merkle 验证；任一失败 = 不通过。"""
        for o in ctx.openings:
            if not verify_opening(o, ctx.commitment):
                return False
        return True

    def execute(
        self, task_binding_hash: str, primitive_id: str, ctx: AuditExecutionContext,
    ) -> PrivacyAuditEvidence:
        """执行一次 COMMIT_CHALLENGE 审计。"""
        if not self.verify_task_binding(task_binding_hash, ctx):
            # 任务绑定失败 → BREACH_EVIDENCE
            return self._evidence(
                ctx, primitive_id, merkle_ok=False,
                result=PrimitiveResult.BREACH_EVIDENCE,
                disclosed_bytes=0, test_statistic=None, p_value=None,
                opening_hashes=[o.opening_hash for o in ctx.openings])

        merkle_ok = self.verify_all_openings(ctx)
        disclosed_bytes = sum(len(o.row_payload) for o in ctx.openings)
        if not merkle_ok:
            return self._evidence(
                ctx, primitive_id, merkle_ok=False,
                result=PrimitiveResult.BREACH_EVIDENCE,
                disclosed_bytes=disclosed_bytes,
                test_statistic=None, p_value=None,
                opening_hashes=[o.opening_hash for o in ctx.openings])

        # Merkle 全通过 → 运行抽样 primitive（只含 k 行）
        out = run_primitive(primitive_id, ctx.openings, ctx.claim)
        return self._evidence(
            ctx, primitive_id, merkle_ok=True,
            result=out.result, disclosed_bytes=disclosed_bytes,
            test_statistic=out.test_statistic, p_value=out.p_value,
            opening_hashes=[o.opening_hash for o in ctx.openings])

    def _evidence(self, ctx, primitive_id, *, merkle_ok, result, disclosed_bytes,
                  test_statistic, p_value, opening_hashes) -> PrivacyAuditEvidence:
        ev = build_evidence(
            node_id=self.node_id, task_id=ctx.challenge.task_binding_hash if ctx.challenge else "",
            execution_mode=AuditExecutionMode.COMMIT_CHALLENGE.value,
            claim_hash=ctx.claim.claim_hash,
            commitment_hash=ctx.commitment.commitment_hash,
            challenge_id=ctx.challenge.challenge_id if ctx.challenge else "",
            challenge_hash=ctx.challenge.challenge_hash if ctx.challenge else "",
            opening_indices=[o.index for o in ctx.openings],
            opening_hashes=opening_hashes,
            merkle_verification_passed=merkle_ok,
            disclosed_bytes=disclosed_bytes,
            test_statistic=test_statistic, p_value=p_value,
            result=result.value,
        )
        return _with_signature(ev, self.signing_key)

    def __init__(self, node_id: str, signing_key=None) -> None:
        self.node_id = node_id
        self.signing_key = signing_key  # SigningKeyPair | None


def _with_signature(ev: PrivacyAuditEvidence, signing_key) -> PrivacyAuditEvidence:
    """P0-F：对 evidence canonical payload（不含 signature）用节点私钥签名。

    无密钥（测试/未配置）→ 空签名；scheduler 将此类证据计为
    INVALID_EVIDENCE_SIGNATURE，不计入 quorum（MFC-G05/G06）。
    """
    if signing_key is None:
        return ev
    from valor.security.signing import sign_evidence

    sig = sign_evidence(signing_key, ev.to_plain())
    return PrivacyAuditEvidence(
        node_id=ev.node_id, task_id=ev.task_id, execution_mode=ev.execution_mode,
        claim_hash=ev.claim_hash, commitment_hash=ev.commitment_hash,
        challenge_id=ev.challenge_id, challenge_hash=ev.challenge_hash,
        opening_indices=ev.opening_indices,
        opening_commitment_hashes=ev.opening_commitment_hashes,
        merkle_verification_passed=ev.merkle_verification_passed,
        disclosed_rows=ev.disclosed_rows, disclosed_bytes=ev.disclosed_bytes,
        test_statistic=ev.test_statistic, p_value=ev.p_value,
        result=ev.result, execution_hash=ev.execution_hash,
        timestamp=ev.timestamp, signature=sig, evidence_id=ev.evidence_id,
    )


__all__ = ["AuditExecutionContext", "CommitChallengeVerifier", "_with_signature"]
