"""反馈与 ground-truth 资格门测试（规范 §45/§46）。"""

from __future__ import annotations

import pytest

from valor.core.errors import VALORError
from valor.feedback.auditor_reliability import update_auditor_beta
from valor.feedback.eligibility import GroundTruthEligibilityGate
from valor.feedback.seller_risk import update_seller_beta


def test_eligibility_gate():
    assert GroundTruthEligibilityGate.is_eligible("STRONG_CHALLENGE")
    assert GroundTruthEligibilityGate.is_eligible("CONTROLLED_CANARY")
    # PASS / TRADE 不具备资格（§45）
    assert not GroundTruthEligibilityGate.is_eligible("PASS")
    assert not GroundTruthEligibilityGate.is_eligible("TRADE")


def test_seller_beta_update_eligible():
    a, b = update_seller_beta(1.0, 1.0, tp=2, fn=1, event_type="ADJUDICATED_DISPUTE")
    assert (a, b) == (3.0, 2.0)


def test_seller_beta_rejects_ineligible():
    with pytest.raises(VALORError):
        update_seller_beta(1.0, 1.0, tp=2, fn=1, event_type="PASS")


def test_auditor_beta_update():
    a, b = update_auditor_beta(1.0, 1.0, correct=5, incorrect=1,
                               event_type="STRONG_CHALLENGE")
    assert (a, b) == (6.0, 2.0)
