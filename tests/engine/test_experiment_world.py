"""Round 6 Phase 3: L-world must be materially different with honest seller."""

from __future__ import annotations

import numpy as np

from valor.engine.experiment_world import build_experiment_world
from valor.engine.scenario import CapstoneScenario
from valor.privacy_audit import CommittedDatasetStore
from valor.core.hashing import content_hash


def _scenario():
    sc = CapstoneScenario(scenario_id="lworld", seller_id="s", buyer_id="b")
    sc.audit["low_suitability_world"] = {
        "method": "buyer_task_utility",
        "threshold": 0.5,
        "row_utilities": [0.1] * 40 + [0.9] * 60,
        "ground_truth_ref": "rcal-L-buyer-task-utility",
    }
    return sc


def _data(n=100, seed=7):
    rng = np.random.default_rng(seed)
    X = rng.integers(0, 256, size=(n, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=n)
    return X, y


def test_L_world_is_materially_different_from_G(tmp_path):
    X, y = _data()
    sc = _scenario()
    store = CommittedDatasetStore(str(tmp_path / "store"))
    g = build_experiment_world(
        scenario=sc, store=store, X=X, y=y, role_id="R_cert", state="G", k=16, run=0)
    l = build_experiment_world(
        scenario=sc, store=store, X=X, y=y, role_id="R_cert", state="L", k=16, run=0)
    assert len(l.y_committed) < len(g.y_committed)
    assert l.construction_hash
    assert l.suitability_metric is not None and l.suitability_metric < l.suitability_threshold


def test_L_world_seller_remains_honest(tmp_path):
    X, y = _data()
    sc = _scenario()
    store = CommittedDatasetStore(str(tmp_path / "store2"))
    l = build_experiment_world(
        scenario=sc, store=store, X=X, y=y, role_id="R_cert", state="L", k=16, run=0)
    rec = store._datasets[l.seller.dataset_id]
    # commitment valid: n_rows matches, no post-commit tamper (stored y equals committed y)
    assert rec["commitment"].n_rows == len(l.y_committed)
    assert np.array_equal(rec["y"], l.y_committed)


def test_L_world_suitability_below_threshold(tmp_path):
    X, y = _data()
    sc = _scenario()
    store = CommittedDatasetStore(str(tmp_path / "store3"))
    g = build_experiment_world(
        scenario=sc, store=store, X=X, y=y, role_id="R_cert", state="G", k=16, run=0)
    l = build_experiment_world(
        scenario=sc, store=store, X=X, y=y, role_id="R_cert", state="L", k=16, run=0)
    threshold = float(sc.audit["low_suitability_world"]["threshold"])
    assert g.suitability_metric >= threshold
    assert l.suitability_metric < threshold


def _breach_scenario(family="POST_COMMIT_DATA_TAMPER"):
    sc = _scenario()
    sc.audit["breach_world"] = {
        "family": family,
        "tamper_fraction": 0.2,
        "ground_truth_ref": f"rcal-B-{family.lower()}",
    }
    return sc


def test_breach_world_post_commit_produces_real_breach_evidence(tmp_path):
    from valor.privacy_audit import ClaimType, claim_from_data
    from valor.privacy_audit.challenge import generate_challenge
    from valor.privacy_audit.opening import make_opening
    from valor.privacy_audit.merkle import MerkleProof
    from valor.privacy_audit.verifier import AuditExecutionContext, CommitChallengeVerifier
    X, y = _data()
    sc = _breach_scenario()
    store = CommittedDatasetStore(str(tmp_path / "bstore"))
    b = build_experiment_world(
        scenario=sc, store=store, X=X, y=y, role_id="R_cert", state="B", k=16, run=0)
    claim = claim_from_data(
        claim_type=ClaimType.LABEL_DISTRIBUTION, X=X, y=b.y_committed,
        dataset_commitment_hash=b.seller.commitment.commitment_hash)
    ch = generate_challenge(
        task_binding_hash="tb", task_hash="tb", action_id="a1",
        n_rows=len(b.y_committed), k=16, nonce=b"salt")
    raw_opens = store.open_rows(b.seller.dataset_id, list(ch.indices))
    opens = [
        make_opening(
            index=o["index"], row_payload=bytes.fromhex(o["row_payload"]),
            salt=bytes.fromhex(o["salt"]),
            proof=MerkleProof.from_plain(o["merkle_proof"]))
        for o in raw_opens
    ]
    verifier = CommitChallengeVerifier("node-0")
    ctx = AuditExecutionContext(
        commitment=b.seller.commitment, claim=claim, challenge=ch, openings=opens)
    ev = verifier.execute("tb", "LabelDistributionAudit", ctx)
    assert ev.result == "BREACH_EVIDENCE"


def test_unsupported_breach_families_fail_closed(tmp_path):
    import pytest
    X, y = _data()
    store = CommittedDatasetStore(str(tmp_path / "bstore2"))
    for family in ("CLAIM_FALSE", "OPENING_TAMPER", "VERSION_MISMATCH"):
        sc = _breach_scenario(family)
        with pytest.raises(ValueError, match="BREACH_FAMILY_NOT_CERTIFIED"):
            build_experiment_world(
                scenario=sc, store=store, X=X, y=y,
                role_id="R_cert", state="B", k=16, run=0)
