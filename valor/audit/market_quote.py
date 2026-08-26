"""Audit Market Quote / Execution Record —— 冻结设计 §25 / Algorithm 2。

把审计市场选择重构为严格的：

    Quote → Choose → Execute

时序（FullChainGate MFC-G02 校验）：
    timestamp(VCG_QUOTE) < timestamp(VOI_DECISION) < timestamp(AUDIT_EXECUTION)

- AuditMarketSnapshot：quote 时冻结的审计市场状态（bids / committee 资格 /
  qualified nodes），禁止 quote 与 execute 之间偷换 bids/committee。
- AuditMarketQuote：对候选 action a_j 的事前报价，含 Reverse VCG 分配、
  反事实分配、逐节点 VCG 支付，以及预期现金成本 MĈ_A^pay(a_j)。
- AuditActionExecutionRecord：执行后的事后记录（quoted_cost / realized_cost /
  quote_error）。

市场状态必须由上游（ExperimentWorld / AuditorMarketSnapshot 注入）提供，
禁止 executor 内部人工生成 bids（如 `10+i`）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash


@dataclass(frozen=True)
class AuditMarketSnapshot:
    """quote 时冻结的审计市场状态（§18/§25）。

    必须由上游注入（ExperimentWorld source_kind=MARKET_DISCOVERED /
    THREAT_SCENARIO），禁止 executor 内部人工生成。
    """

    snapshot_id: str
    family: str
    qualified_nodes: list[str]  # 具备 capability/stake/availability 的合格节点
    bids: dict[str, float]  # node_id -> reported cost
    min_stake: float
    timestamp: str = ""
    source_kind: str = "MARKET_DISCOVERED"
    source_ref: str = ""
    version: str = "1"
    capability: dict[str, list[str]] = field(default_factory=dict)
    stake: dict[str, float] = field(default_factory=dict)
    availability: dict[str, float] = field(default_factory=dict)
    reliability: dict[str, float] = field(default_factory=dict)
    public_key_fingerprint: dict[str, str] = field(default_factory=dict)

    @property
    def snapshot_hash(self) -> str:
        return content_hash({
            "snapshot_id": self.snapshot_id, "family": self.family,
            "qualified_nodes": sorted(self.qualified_nodes),
            "bids": {k: float(v) for k, v in sorted(self.bids.items())},
            "min_stake": self.min_stake, "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "version": self.version,
            "capability": {k: sorted(v) for k, v in sorted(self.capability.items())},
            "stake": {k: float(v) for k, v in sorted(self.stake.items())},
            "availability": {k: float(v) for k, v in sorted(self.availability.items())},
            "reliability": {k: float(v) for k, v in sorted(self.reliability.items())},
            "public_key_fingerprint": {k: v for k, v in sorted(self.public_key_fingerprint.items())},
        })

    def to_plain(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id, "family": self.family,
            "qualified_nodes": self.qualified_nodes,
            "bids": self.bids, "min_stake": self.min_stake,
            "timestamp": self.timestamp, "source_kind": self.source_kind,
            "source_ref": self.source_ref, "version": self.version,
            "capability": self.capability, "stake": self.stake,
            "availability": self.availability, "reliability": self.reliability,
            "public_key_fingerprint": self.public_key_fingerprint,
            "snapshot_hash": self.snapshot_hash,
        }


@dataclass(frozen=True)
class AuditMarketQuote:
    """对候选 action a_j 的事前报价（§25 MĈ_A^pay）。

    冻结 snapshot + Reverse VCG 分配 + 预期现金成本。VOI 决策只允许使用
    quote 的 expected_cash_cost（禁止 config cost / 0.0 / 人工 expected cost）。
    """

    action_id: str
    action_profile_hash: str
    market_snapshot_hash: str
    snapshot: AuditMarketSnapshot
    committee: list[str]
    bids: dict[str, float]
    vcg_payments: dict[str, float]
    expected_vcg_payment: float
    expected_chain_fee: float
    expected_challenge_cost: float
    expected_dispute_cost: float
    expected_cash_cost: float  # = 上述四项之和
    expected_vcg_payments_by_node: dict[str, float] = field(default_factory=dict)
    expected_vcg_payment_total: float = 0.0
    payer: str = "SELLER"
    trigger: str = "BASE_LISTING"
    quote_time: str = ""
    quote_seq: int = 0
    source_kind: str = "MARKET_DISCOVERED"
    source_ref: str = ""
    version: str = "1"

    @property
    def quote_hash(self) -> str:
        return content_hash({
            "action_id": self.action_id,
            "action_profile_hash": self.action_profile_hash,
            "market_snapshot_hash": self.market_snapshot_hash,
            "committee": sorted(self.committee),
            "expected_vcg_payments_by_node": {k: float(v) for k, v in sorted(self.expected_vcg_payments_by_node.items())},
            "expected_vcg_payment_total": self.expected_vcg_payment_total,
            "vcg_payments": {k: float(v) for k, v in sorted(self.vcg_payments.items())},
            "expected_vcg_payment": self.expected_vcg_payment,
            "expected_chain_fee": self.expected_chain_fee,
            "expected_challenge_cost": self.expected_challenge_cost,
            "expected_dispute_cost": self.expected_dispute_cost,
            "expected_cash_cost": self.expected_cash_cost,
            "payer": self.payer, "trigger": self.trigger,
            "quote_time": self.quote_time,
            "quote_seq": self.quote_seq,
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "version": self.version,
        })

    def to_plain(self) -> dict:
        return {
            "action_id": self.action_id,
            "action_profile_hash": self.action_profile_hash,
            "market_snapshot_hash": self.market_snapshot_hash,
            "snapshot": self.snapshot.to_plain(),
            "committee": self.committee, "bids": self.bids,
            "vcg_payments": self.vcg_payments,
            "expected_vcg_payment": self.expected_vcg_payment,
            "expected_vcg_payments_by_node": self.expected_vcg_payments_by_node,
            "expected_vcg_payment_total": self.expected_vcg_payment_total,
            "expected_chain_fee": self.expected_chain_fee,
            "expected_challenge_cost": self.expected_challenge_cost,
            "expected_dispute_cost": self.expected_dispute_cost,
            "expected_cash_cost": self.expected_cash_cost,
            "payer": self.payer, "trigger": self.trigger,
            "quote_time": self.quote_time, "quote_hash": self.quote_hash,
            "quote_seq": self.quote_seq,
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "version": self.version,
        }


@dataclass
class AuditActionExecutionRecord:
    """一次已执行 action 的事后记录（Quote→Choose→Execute 的 Execute 段）。"""

    action_id: str
    quote_hash: str
    market_snapshot_hash: str
    committee: list[str]
    quoted_cost: float
    realized_cost: float
    quote_error: float  # realized - quoted
    vcg_payments_realized: dict[str, float]
    outcome: str
    execution_time: str = ""
    evidence_hashes: list[str] = field(default_factory=list)
    status: str = "CERTIFIED"

    def to_plain(self) -> dict:
        return {
            "action_id": self.action_id, "quote_hash": self.quote_hash,
            "market_snapshot_hash": self.market_snapshot_hash,
            "committee": self.committee, "quoted_cost": self.quoted_cost,
            "realized_cost": self.realized_cost,
            "quote_error": self.quote_error,
            "vcg_payments_realized": self.vcg_payments_realized,
            "outcome": self.outcome, "execution_time": self.execution_time,
            "evidence_hashes": self.evidence_hashes, "status": self.status,
        }


def build_quote(
    *,
    action_id: str,
    action_profile_hash: str,
    snapshot: AuditMarketSnapshot,
    m: int,
    min_stake: float,
    payer: str = "SELLER",
    trigger: str = "BASE_LISTING",
    expected_chain_fee: float = 0.0,
    expected_challenge_cost: float = 0.0,
    expected_dispute_cost: float = 0.0,
    quote_time: str = "",
    quote_seq: int = 0,
    source_kind: str = "MARKET_DISCOVERED",
    source_ref: str = "",
    version: str = "1",
) -> AuditMarketQuote:
    """从冻结 market snapshot 生成一次 Reverse VCG 报价（§25）。

    使用真实市场 bids（snapshot.bids）+ 精确 Reverse VCG。若委员会不可行
    （counterfactual infeasible），抛 CounterfactualInfeasibleError。
    """
    from valor.core.errors import CounterfactualInfeasibleError
    from valor.core.ids import AuditorID
    from valor.distributed.node_state import NodeRegistry
    from valor.market.reverse_vcg import reverse_vcg_payments

    # 用 snapshot 的 qualified nodes 构造 registry（只含合格节点）
    reg = NodeRegistry()
    for nid in snapshot.qualified_nodes:
        from valor.distributed.node_state import AuditorNode

        reg.register(AuditorNode(
            node_id=AuditorID(nid), capability=(snapshot.family,),
            availability=1.0, stake=snapshot.min_stake))
    try:
        payments, _cf = reverse_vcg_payments(
            reg, family=snapshot.family, m=m,
            bids={AuditorID(k): v for k, v in snapshot.bids.items()},
            min_stake=min_stake)
    except CounterfactualInfeasibleError:
        raise
    committee = [str(nid) for nid in payments]
    expected_vcg = float(sum(payments.values()))
    expected_cash_cost = (
        expected_vcg + expected_chain_fee + expected_challenge_cost
        + expected_dispute_cost)
    return AuditMarketQuote(
        action_id=action_id, action_profile_hash=action_profile_hash,
        market_snapshot_hash=snapshot.snapshot_hash,
        snapshot=snapshot, committee=committee,
        bids=dict(snapshot.bids),
        vcg_payments={str(k): v for k, v in payments.items()},
        expected_vcg_payment=expected_vcg,
        expected_vcg_payments_by_node={str(k): v for k, v in payments.items()},
        expected_vcg_payment_total=expected_vcg,
        expected_chain_fee=expected_chain_fee,
        expected_challenge_cost=expected_challenge_cost,
        expected_dispute_cost=expected_dispute_cost,
        expected_cash_cost=expected_cash_cost,
        payer=payer, trigger=trigger, quote_time=quote_time,
        quote_seq=quote_seq,
        source_kind=source_kind, source_ref=source_ref, version=version,
    )


__all__ = [
    "AuditMarketSnapshot", "AuditMarketQuote", "AuditActionExecutionRecord",
    "build_quote",
]


@dataclass(frozen=True)
class FrozenAuditDecisionRecord:
    """Frozen per-candidate audit decision artifact (Round 6 Phase 9).

    Captures the exact quote and VOI inputs used before any audit execution.
    """

    action_profile_hash: str
    likelihood_artifact_hash: str
    quote_hash: str
    market_snapshot_hash: str
    quoted_committee: list[str]
    quoted_vcg_payments: dict[str, float]
    expected_chain_fee: float
    expected_challenge_cost: float
    expected_dispute_cost: float
    expected_cash_cost: float
    MV: float
    VOI: float

    @property
    def record_hash(self) -> str:
        return content_hash({
            "action_profile_hash": self.action_profile_hash,
            "likelihood_artifact_hash": self.likelihood_artifact_hash,
            "quote_hash": self.quote_hash,
            "market_snapshot_hash": self.market_snapshot_hash,
            "quoted_committee": sorted(self.quoted_committee),
            "quoted_vcg_payments": {k: float(v) for k, v in sorted(self.quoted_vcg_payments.items())},
            "expected_chain_fee": self.expected_chain_fee,
            "expected_challenge_cost": self.expected_challenge_cost,
            "expected_dispute_cost": self.expected_dispute_cost,
            "expected_cash_cost": self.expected_cash_cost,
            "MV": self.MV,
            "VOI": self.VOI,
        })

    def to_plain(self) -> dict:
        return {
            "action_profile_hash": self.action_profile_hash,
            "likelihood_artifact_hash": self.likelihood_artifact_hash,
            "quote_hash": self.quote_hash,
            "market_snapshot_hash": self.market_snapshot_hash,
            "quoted_committee": self.quoted_committee,
            "quoted_vcg_payments": {str(k): float(v) for k, v in self.quoted_vcg_payments.items()},
            "expected_chain_fee": self.expected_chain_fee,
            "expected_challenge_cost": self.expected_challenge_cost,
            "expected_dispute_cost": self.expected_dispute_cost,
            "expected_cash_cost": self.expected_cash_cost,
            "MV": self.MV,
            "VOI": self.VOI,
            "record_hash": self.record_hash,
        }


@dataclass(frozen=True)
class AuditExecutionRecord:
    """Post-execution audit action record bound to the frozen quote."""

    action_id: str
    selected_quote_hash: str
    selected_action_profile_hash: str
    selected_market_snapshot_hash: str
    realized_committee: list[str]
    realized_vcg: dict[str, float]
    realized_cost: float

    @property
    def record_hash(self) -> str:
        return content_hash({
            "action_id": self.action_id,
            "selected_quote_hash": self.selected_quote_hash,
            "selected_action_profile_hash": self.selected_action_profile_hash,
            "selected_market_snapshot_hash": self.selected_market_snapshot_hash,
            "realized_committee": sorted(self.realized_committee),
            "realized_vcg": {k: float(v) for k, v in sorted(self.realized_vcg.items())},
            "realized_cost": self.realized_cost,
        })

    def to_plain(self) -> dict:
        return {
            "action_id": self.action_id,
            "selected_quote_hash": self.selected_quote_hash,
            "selected_action_profile_hash": self.selected_action_profile_hash,
            "selected_market_snapshot_hash": self.selected_market_snapshot_hash,
            "realized_committee": self.realized_committee,
            "realized_vcg": {str(k): float(v) for k, v in self.realized_vcg.items()},
            "realized_cost": self.realized_cost,
            "record_hash": self.record_hash,
        }


__all__ = [
    "AuditMarketSnapshot", "AuditMarketQuote", "AuditActionExecutionRecord",
    "FrozenAuditDecisionRecord", "AuditExecutionRecord",
]
