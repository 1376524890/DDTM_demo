"""对象绑定与承诺校验（规范 §4）。

每笔交易承诺 τ = (txID, sellerID, buyerID, assetID, versionID,
H(D), H(M_D), H(R_τ), policyVersion, timestamp)。

必须满足：
    D_valuation = D_quality = D_audit = D_delivery   （同一对象承诺）
    H(R_authorization) = H(R_τ)                       （权利束承诺一致）

任何对象哈希、版本或权利束不一致均为确定性合同错误（CommitBindingError）；
若来自卖方替换或虚假交付，则进入 SELLER_BREACH（此处只负责检测不一致）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from valor.core.errors import CommitBindingError
from valor.core.hashing import content_hash


@dataclass(frozen=True)
class TransactionCommitment:
    """交易承诺 τ（规范 §4）。"""

    tx_id: str
    seller_id: str
    buyer_id: str
    asset_id: str
    version_id: str
    data_commitment: str
    metadata_commitment: str
    rights_commitment: str
    policy_version: str
    timestamp: str


@dataclass(frozen=True)
class BoundObject:
    """一个参与对象承诺（数据 / 元数据 / 权利束）。"""

    data_commitment: str = ""
    metadata_commitment: str = ""
    rights_commitment: str = ""


def bind_commitment(*, data: str, metadata: str, rights: str) -> str:
    """对 (H(D), H(M_D), H(R_τ)) 三元组生成绑定哈希。

    用于把同一对象在估值/质量/审计/交付各环节的绑定统一到一个可校验摘要。
    """
    return content_hash(
        {"data": data, "metadata": metadata, "rights": rights}
    )


def verify_single_object_binding(bound: BoundObject, *, what: str) -> None:
    """校验单个对象的 data/metadata/rights 承诺非空；否则为绑定不完整。

    对应规范 §4 的 H(R_authorization)=H(R_τ) 与对象承诺必须一致的原则。
    """
    if not bound.data_commitment:
        raise CommitBindingError(f"[{what}] 缺少数据承诺 H(D)")
    if not bound.metadata_commitment:
        raise CommitBindingError(f"[{what}] 缺少元数据承诺 H(M_D)")
    if not bound.rights_commitment:
        raise CommitBindingError(f"[{what}] 缺少权利束承诺 H(R_τ)")


def verify_commitment(
    expected: TransactionCommitment,
    observed: BoundObject,
    *,
    what: str,
) -> None:
    """校验观测对象承诺与交易承诺一致（规范 §4 对象绑定）。

    任意不一致均抛 CommitBindingError（确定性合同错误）。
    """
    verify_single_object_binding(observed, what=what)
    if observed.data_commitment != expected.data_commitment:
        raise CommitBindingError(
            f"[{what}] 数据承诺不一致: 期望 {expected.data_commitment}，"
            f"实际 {observed.data_commitment}"
        )
    if observed.metadata_commitment != expected.metadata_commitment:
        raise CommitBindingError(f"[{what}] 元数据承诺不一致")
    if observed.rights_commitment != expected.rights_commitment:
        raise CommitBindingError(f"[{what}] 权利束承诺不一致（H(R_τ) 不匹配）")
