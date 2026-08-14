"""数据集清单（DatasetManifest）。

记录数据集各角色划分、文件哈希与来源，供复现与对象绑定使用。
对齐规范 §55 四角色划分、§4 对象承诺。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash


@dataclass(frozen=True)
class DatasetManifest:
    """数据集清单。

    role_files 把不同角色（base_train/seller_pool/valuation_validation/
    final_evaluation 等）映射到文件与哈希，满足规范 §55 的四角色划分可追溯。
    """

    dataset_name: str
    version: str
    role_files: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def file_hashes(self) -> dict[str, str]:
        """返回 {role: {filepath: sha256}}。"""
        return {
            role: {f["path"]: f["sha256"] for f in files}
            for role, files in self.role_files.items()
        }

    @property
    def manifest_hash(self) -> str:
        """清单确定性哈希。"""
        return content_hash(
            {
                "dataset_name": self.dataset_name,
                "version": self.version,
                "role_files": self.role_files,
            }
        )

    def to_plain(self) -> dict:
        return {
            "dataset_name": self.dataset_name,
            "version": self.version,
            "role_files": self.role_files,
            "manifest_hash": self.manifest_hash,
            "extra": self.extra,
        }
