"""valor/asset 单元测试：资产承诺 / 对象绑定 / 资格 / 合规（规范 §3、§4、§6）。"""

from __future__ import annotations

import pytest

from valor.asset import (
    AssetVersion,
    Compliant,
    DataAsset,
    Entitled,
    TransactionCommitment,
    verify_commitment,
)
from valor.asset.commitments import BoundObject
from valor.core.errors import CommitBindingError, EntitlementError


def _commitment() -> TransactionCommitment:
    return TransactionCommitment(
        tx_id="tx-1",
        seller_id="s1",
        buyer_id="b1",
        asset_id="a1",
        version_id="v1",
        data_commitment="a" * 64,
        metadata_commitment="b" * 64,
        rights_commitment="c" * 64,
        policy_version="p1",
        timestamp="2025-01-01T00:00:00Z",
    )


def test_asset_version_requires_valid_commitments():
    with pytest.raises(CommitBindingError):
        DataAsset(
            asset_id="a1",
            versions=(
                AssetVersion(
                    asset_id="a1", version_id="v1",
                    data_commitment="short", metadata_commitment="b" * 64,
                ),
            ),
        )


def test_verify_commitment_ok():
    c = _commitment()
    bound = BoundObject(data_commitment=c.data_commitment,
                        metadata_commitment=c.metadata_commitment,
                        rights_commitment=c.rights_commitment)
    verify_commitment(c, bound, what="valuation")  # 不抛错即通过


def test_verify_commitment_mismatch():
    c = _commitment()
    bound = BoundObject(data_commitment="d" * 64,
                        metadata_commitment=c.metadata_commitment,
                        rights_commitment=c.rights_commitment)
    with pytest.raises(CommitBindingError):
        verify_commitment(c, bound, what="audit")


def test_entitled_gate():
    Entitled(grant_authority=True, version_revoked=False).enforce()
    with pytest.raises(EntitlementError):
        Entitled(grant_authority=True, version_revoked=True).enforce()
    with pytest.raises(EntitlementError):
        Entitled(grant_authority=False, version_revoked=False).enforce()


def test_compliant_gate():
    Compliant(buyer_eligible=True, menu_conflict=False).enforce()
    with pytest.raises(EntitlementError):
        Compliant(buyer_eligible=False, menu_conflict=False).enforce()
