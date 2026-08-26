"""Round 6 Phase 11: action profile binds every behavior-changing field."""

from __future__ import annotations

from valor.audit.action_profile import action_from_profile, build_action_profile


def _audit():
    return {
        "rho": 0.0, "eta_b": 0.1, "eta_o": 0.0, "min_stake": 0.0,
        "alpha_shift": 0.01, "label_error_threshold": 0.28,
        "execution_version_hash": "cc-audit-v1",
        "timeout_s": 10.0,
    }


def test_profile_hash_changes_when_decision_rule_mutates():
    p1 = build_action_profile(scenario_audit=_audit(), claim_type="LABEL_DISTRIBUTION",
                              k=32, f=2)
    p2 = build_action_profile(scenario_audit=_audit(), claim_type="LABEL_DISTRIBUTION",
                              k=32, f=2)
    assert p1.action_profile_hash == p2.action_profile_hash
    a2 = _audit()
    a2["decision_rule_id"] = "DIFFERENT_GOF"
    p3 = build_action_profile(scenario_audit=a2, claim_type="LABEL_DISTRIBUTION",
                              k=32, f=2)
    assert p3.action_profile_hash != p1.action_profile_hash
    action = action_from_profile(p3)
    assert action.decision_rule_id == "DIFFERENT_GOF"
