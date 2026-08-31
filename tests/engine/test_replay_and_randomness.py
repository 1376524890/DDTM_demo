"""Round 7: RandomnessManifest + ReplayVerificationArtifact."""

from __future__ import annotations

from valor.engine.randomness_manifest import RandomnessManifest, ProtectedRandomnessStore
from valor.engine.replay import ReplayVerificationArtifact


def test_randomness_manifest_roundtrip(tmp_path):
    m = RandomnessManifest(run_id="run-1", logical_clock_origin="L0")
    m.add(kind="dataset_commitment", reference="abc", producer="DatasetCommitment")
    m.add(kind="audit_challenge", reference="def", producer="Scheduler")
    plain = m.to_plain()
    m2 = RandomnessManifest.from_plain(plain)
    assert m2.artifact_hash == m.artifact_hash
    assert m2.entries["dataset_commitment"].reference == "abc"


def test_protected_store_does_not_leak_secret(tmp_path):
    store = ProtectedRandomnessStore(tmp_path / "private")
    ref = store.store(kind="challenge_nonce", data=b"secret-bytes")
    assert b"secret-bytes" not in ref.encode()
    assert store.resolve("challenge_nonce", ref) == b"secret-bytes"
    try:
        store.resolve("challenge_nonce", "deadbeef" * 8)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("missing randomness should raise")


def test_replay_artifact_pass_and_mismatch():
    art = ReplayVerificationArtifact(
        original_run_hash="a", replay_run_hash="b",
        randomness_manifest_hash="r",
        decision_equality=True, terminal_equality=True,
        pricing_equality=True, commitment_equality=True,
        posterior_equality=True, provenance_root_equality=True,
        nested_replay_status="COMPLETE",
    )
    assert art.status == "PASS"
    assert not art.mismatch_list

    bad = ReplayVerificationArtifact(
        original_run_hash="a", replay_run_hash="b",
        randomness_manifest_hash="r",
        decision_equality=False, terminal_equality=True,
        pricing_equality=True, commitment_equality=True,
        posterior_equality=True, provenance_root_equality=True,
        mismatch_list=["decision differed"],
        nested_replay_status="COMPLETE",
    )
    assert bad.status == "FAIL"

    skipped = ReplayVerificationArtifact(
        original_run_hash="a", replay_run_hash="b",
        randomness_manifest_hash="r",
        decision_equality=True, terminal_equality=True,
        pricing_equality=True, commitment_equality=True,
        posterior_equality=True, provenance_root_equality=True,
    )
    assert skipped.status == "REPLAY_SKIPPED_NESTED"
