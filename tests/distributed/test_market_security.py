"""市场（Reverse VCG）与安全（BFT/liveness/stake）单元测试（规范 §18-§20）。"""

from __future__ import annotations

import pytest

from valor.core.errors import CounterfactualInfeasibleError
from valor.core.ids import AuditorID
from valor.distributed.node_state import AuditorNode, NodeRegistry
from valor.market.reverse_vcg import reverse_vcg_payments
from valor.security.bft import (
    bft_committee_size,
    p_live_binomial,
    p_safe_binomial,
)
from valor.security.slashing import minimum_auditor_stake


def _registry(n: int) -> NodeRegistry:
    r = NodeRegistry()
    for i in range(n):
        r.register(AuditorNode(
            node_id=AuditorID(f"node-{i}"),
            capability=("structural",), availability=1.0, stake=100.0,
        ))
    return r


def test_bft_committee_size():
    assert bft_committee_size(0) == (1, 1)
    assert bft_committee_size(2) == (7, 5)
    assert bft_committee_size(3) == (10, 7)


def test_p_safe_p_live():
    # f=2, m=7, q=5，η_B=0, η_O=0 → P_safe=P_live=1
    assert p_safe_binomial(7, 2, 0.0) == pytest.approx(1.0)
    assert p_live_binomial(7, 5, 0.0, 0.0) == pytest.approx(1.0)
    # 有拜占庭/离线时 P_safe 下降
    assert p_safe_binomial(7, 2, 0.5) < 1.0


def test_reverse_vcg_payment():
    reg = _registry(7)
    bids = {AuditorID(f"node-{i}"): 10.0 + i for i in range(7)}
    payments, cfcosts = reverse_vcg_payments(
        reg, family="structural", m=5, bids=bids, min_stake=0.0
    )
    # 5 个 winner，支付非负且 ≥ bid
    assert len(payments) == 5
    for nid, p in payments.items():
        assert p >= bids[nid]


def test_counterfactual_infeasible():
    # 只有 m 个候选，删除任一 winner 后无替补 → COUNTERFACTUAL_INFEASIBLE
    reg = _registry(3)
    bids = {AuditorID(f"node-{i}"): 10.0 for i in range(3)}
    with pytest.raises(CounterfactualInfeasibleError):
        reverse_vcg_payments(reg, family="structural", m=3, bids=bids)


def test_min_auditor_stake():
    stake = minimum_auditor_stake(
        g_dev=100.0, epsilon_a=1.0, rho=0.1, p_v=1.0, lambda_a=0.5
    )
    assert stake == pytest.approx(2020.0)
    with pytest.raises(Exception):
        minimum_auditor_stake(
            g_dev=100.0, epsilon_a=1.0, rho=0.0, p_v=1.0, lambda_a=0.5
        )
