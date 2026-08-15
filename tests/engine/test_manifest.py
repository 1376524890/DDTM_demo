"""P0 RunManifest 测试。"""

from __future__ import annotations

import pytest

from valor.engine.manifest import RunManifest, default_manifest


def _full_manifest(**over):
    m = default_manifest(
        run_id="run-abc", tx_id="tx-1",
        config_hash="c" * 64, dataset_hash="d" * 64, seed=42,
    )
    m.set(
        split_hash="s" * 64,
        parameter_manifest_hash="p" * 64,
        trainer_hash="t" * 64,
        model_config_hash="m" * 64,
        dependency_lock_hash="l" * 64,
        valuation_calibration_hash="v" * 64,
        action_catalog_hash="a" * 64,
        audit_policy_hash="u" * 64,
        certificate_hash="e" * 64,
    )
    return m


def test_freeze_requires_all():
    m = RunManifest().set(run_id="run-1", tx_id="tx-1", seed=1)
    with pytest.raises(ValueError, match="缺 required"):
        m.freeze()


def test_freeze_success_and_frozen():
    m = _full_manifest()
    m.freeze()
    assert m._frozen
    assert m.git_commit  # 自动填充
    assert m.manifest_hash
    with pytest.raises(ValueError, match="已冻结"):
        m.set(run_id="other")


def test_hash_deterministic_roundtrip():
    m = _full_manifest()
    m.freeze()
    plain = m.to_plain()
    m2 = RunManifest.from_plain(plain)
    assert m2.to_plain() == plain


def test_different_seed_different_hash():
    a = _full_manifest(seed=1)
    a.freeze()
    b = _full_manifest(seed=2)
    b.freeze()
    assert a.manifest_hash != b.manifest_hash
