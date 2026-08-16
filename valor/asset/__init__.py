"""数据资产 / 版本 / 清单 / 承诺 / 资格 / 合规（规范 §3、§4、§6）。

- models:      DataAsset / AssetVersion（§3.1）
- manifest:    数据集清单（含哈希）
- commitments: 对象绑定与承诺校验（§4）
- entitlement: Entitled(S, A_D, R_τ) 资格硬门槛（§6）
- compliance:  Compliant(A_D, R_τ, B) 合规硬门槛（§6）
"""

from .models import AssetVersion, DataAsset
from .commitments import (
    BoundObject,
    DatasetCommitment,
    TransactionCommitment,
    bind_commitment,
    verify_commitment,
    verify_single_object_binding,
)
from .entitlement import Entitled
from .compliance import Compliant
from .manifest import DatasetManifest

__all__ = [
    "AssetVersion",
    "DataAsset",
    "BoundObject",
    "DatasetCommitment",
    "TransactionCommitment",
    "bind_commitment",
    "verify_commitment",
    "verify_single_object_binding",
    "Entitled",
    "Compliant",
    "DatasetManifest",
]
