"""Round 4 Phase 3: LikelihoodCatalog + canonical action profile identity."""

from __future__ import annotations

import pytest

from valor.audit.action_profile import AuditActionProfile
from valor.audit.likelihood_catalog import FrozenLikelihoodArtifact, LikelihoodCatalog


def _profile(k: int) -> AuditActionProfile:
    return AuditActionProfile(
        action_id=f"LABEL_DISTRIBUTION_CC_{k}",
        primitive_id="LabelDistributionAudit",
        execution_mode="COMMIT_CHALLENGE",
        breach_family="quality",
        claim_type="LABEL_DISTRIBUTION",
        challenge_k=k,
        sampling_method="uniform_random",
        committee_m=7,
        quorum_q=5,
        byzantine_f=2,
        rho=0.0,
        eta_b=0.1,
        eta_o=0.0,
        min_stake=0.0,
        aggregation_rule="quorum-by-result",
        signature_requirement="REQUIRED",
        challenge_policy="rho-sampled",
        disclosure_policy="rows-fraction-bytes",
        timeout_replacement_policy="offline-replacement",
        payer="SELLER",
        trigger="BASE_LISTING",
        security_profile="COMMIT_CHALLENGE",
        decision_thresholds={"alpha_shift": 0.01, "label_error_threshold": 0.28},
        execution_version_hash="cc-audit-v1",
    )


def _artifact(profile: AuditActionProfile) -> FrozenLikelihoodArtifact:
    return FrozenLikelihoodArtifact(
        action_profile_hash=profile.action_profile_hash,
        action_id=profile.action_id,
        calibration_role_hash="R_cal-v1",
        outcome_vocabulary_version="v1",
        counts={
            "G": {"PASS": 10, "CLAIM_NOT_SUPPORTED": 1},
            "L": {"CLAIM_NOT_SUPPORTED": 8, "INCONCLUSIVE": 1},
            "B": {"BREACH_EVIDENCE": 9, "PASS": 1},
        },
        dirichlet_prior={"PASS": 1.0, "CLAIM_NOT_SUPPORTED": 1.0,
                         "BREACH_EVIDENCE": 1.0, "INCONCLUSIVE": 1.0},
        likelihood_rows={
            "PASS": {"G": 0.8, "L": 0.1, "B": 0.1},
            "CLAIM_NOT_SUPPORTED": {"G": 0.1, "L": 0.8, "B": 0.1},
            "BREACH_EVIDENCE": {"G": 0.1, "L": 0.1, "B": 0.8},
        },
        calibration_code_hash="cal" * 16,
        raw_event_refs=["rcal://evt-1"],
    )


def test_likelihood_catalog_resolves_profile_hash():
    p32 = _profile(32)
    p64 = _profile(64)
    cat = LikelihoodCatalog()
    cat.register(_artifact(p32))
    art = cat.resolve(p32.action_profile_hash)
    assert art.action_id == "LABEL_DISTRIBUTION_CC_32"
    assert art.artifact_hash
    with pytest.raises(KeyError):
        cat.resolve(p64.action_profile_hash)


def test_profile_hash_changes_with_k():
    assert _profile(32).action_profile_hash != _profile(64).action_profile_hash
