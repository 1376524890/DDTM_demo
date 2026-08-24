"""R_cal / R_cert / R_eval 三集合隔离（EF-G03）。

强制：R_cal ∩ R_cert = R_cal ∩ R_eval = R_cert ∩ R_eval = ∅。
    - likelihood 从 R_cal 得
    - p̲_B^sys certificate 从 R_cert 得
    - RQ metrics 从 R_eval 得
正式论文结果只能来自 R_eval。

隔离比较的是 immutable sample IDs（DataRoleManifest.sample_ids），不是 event IDs
或 world IDs。DataRoleRegistry.freeze() 在任何 overlap 时抛 DataSplitIsolationError，
formal mode fail closed。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from valor.core.hashing import content_hash


class DataSplitIsolationError(Exception):
    """三集合交叉 → 隔离失败。"""


@dataclass(frozen=True)
class DataRoleManifest:
    """一个数据角色（R_cal / R_cert / R_eval）的不可变样本清单（Round 5 §2）。

    必须记录 immutable sample IDs，而不是 event IDs；sample_ids_hash 由
    canonical sorted sample IDs 派生。所有 hash 字段必须来自上游 artifact /
    显式输入，禁止占位字符串。
    """

    role_id: str
    dataset_id: str
    dataset_version: str
    sample_ids: tuple[int, ...]
    split_seed: int
    split_algorithm_hash: str
    source_dataset_hash: str
    trainer_scope_hash: str
    task_family_hash: str
    created_from_manifest_hash: str = ""

    @property
    def sample_ids_hash(self) -> str:
        return content_hash({
            "role_id": self.role_id,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "sample_ids": sorted(int(x) for x in self.sample_ids),
        })

    @property
    def role_manifest_hash(self) -> str:
        return content_hash(self.to_plain())

    def to_plain(self) -> dict:
        return {
            "role_id": self.role_id,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "sample_ids": sorted(int(x) for x in self.sample_ids),
            "sample_ids_hash": self.sample_ids_hash,
            "split_seed": self.split_seed,
            "split_algorithm_hash": self.split_algorithm_hash,
            "source_dataset_hash": self.source_dataset_hash,
            "trainer_scope_hash": self.trainer_scope_hash,
            "task_family_hash": self.task_family_hash,
            "created_from_manifest_hash": self.created_from_manifest_hash,
        }

    def to_plain_with_hash(self) -> dict:
        d = self.to_plain()
        d["role_manifest_hash"] = self.role_manifest_hash
        return d

    @classmethod
    def from_plain(cls, d: dict) -> "DataRoleManifest":
        return cls(
            role_id=d["role_id"],
            dataset_id=d["dataset_id"],
            dataset_version=d["dataset_version"],
            sample_ids=tuple(int(x) for x in d["sample_ids"]),
            split_seed=int(d["split_seed"]),
            split_algorithm_hash=d["split_algorithm_hash"],
            source_dataset_hash=d["source_dataset_hash"],
            trainer_scope_hash=d["trainer_scope_hash"],
            task_family_hash=d["task_family_hash"],
            created_from_manifest_hash=d.get("created_from_manifest_hash", ""),
        )


@dataclass
class DataRoleRegistry:
    """数据角色注册表：world_id / dataset indices / seeds 三集合隔离。"""

    calibration_worlds: set[str] = field(default_factory=set)
    certification_worlds: set[str] = field(default_factory=set)
    evaluation_worlds: set[str] = field(default_factory=set)
    calibration_seeds: set[int] = field(default_factory=set)
    certification_seeds: set[int] = field(default_factory=set)
    evaluation_seeds: set[int] = field(default_factory=set)
    # Round 5: immutable sample-ID based manifests (role_id -> DataRoleManifest)
    role_manifests: dict[str, DataRoleManifest] = field(default_factory=dict)
    frozen: bool = False

    def assign_world(self, world_id: str, role: str) -> None:
        """把 world 分配到角色；若已在他角色 → 抛隔离错误。"""
        target = {
            "calibration": self.calibration_worlds,
            "certification": self.certification_worlds,
            "evaluation": self.evaluation_worlds,
        }.get(role)
        if target is None:
            raise ValueError(f"未知角色 {role}")
        others = {
            "calibration": self.certification_worlds | self.evaluation_worlds,
            "certification": self.calibration_worlds | self.evaluation_worlds,
            "evaluation": self.calibration_worlds | self.certification_worlds,
        }[role]
        if world_id in others:
            raise DataSplitIsolationError(
                f"world {world_id} 已存在于其他角色集合")
        target.add(world_id)

    def assign_seed(self, seed: int, role: str) -> None:
        target = {
            "calibration": self.calibration_seeds,
            "certification": self.certification_seeds,
            "evaluation": self.evaluation_seeds,
        }.get(role)
        if target is None:
            raise ValueError(f"未知角色 {role}")
        others = {
            "calibration": self.certification_seeds | self.evaluation_seeds,
            "certification": self.calibration_seeds | self.evaluation_seeds,
            "evaluation": self.calibration_seeds | self.certification_seeds,
        }[role]
        if seed in others:
            raise DataSplitIsolationError(f"seed {seed} 已存在于其他角色集合")
        target.add(seed)

    def validate_isolation(self) -> bool:
        """校验三集合两两不相交。"""
        return (
            self.calibration_worlds.isdisjoint(self.certification_worlds)
            and self.calibration_worlds.isdisjoint(self.evaluation_worlds)
            and self.certification_worlds.isdisjoint(self.evaluation_worlds)
            and self.calibration_seeds.isdisjoint(self.certification_seeds)
            and self.calibration_seeds.isdisjoint(self.evaluation_seeds)
            and self.certification_seeds.isdisjoint(self.evaluation_seeds)
        )

    def register_role_manifest(self, manifest: DataRoleManifest) -> None:
        """注册一个角色 manifest；freeze 前允许，freeze 后抛错。"""
        if self.frozen:
            raise DataSplitIsolationError("DATA_ROLE_OVERLAP: registry frozen")
        if manifest.role_id in self.role_manifests:
            raise ValueError(f"重复角色 manifest: {manifest.role_id}")
        self.role_manifests[manifest.role_id] = manifest

    def freeze(self, *, formal: bool = True) -> dict:
        """硬检查三集合 sample-ID 两两不相交；任何 overlap -> DATA_ROLE_OVERLAP。"""
        self.frozen = True
        names = sorted(self.role_manifests)
        overlap: dict[str, list[str]] = {}
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a = set(self.role_manifests[names[i]].sample_ids)
                b = set(self.role_manifests[names[j]].sample_ids)
                inter = sorted(int(x) for x in (a & b))
                if inter:
                    overlap[f"{names[i]} ∩ {names[j]}"] = inter
        if overlap:
            raise DataSplitIsolationError(
                f"DATA_ROLE_OVERLAP: {overlap}")
        return self.to_plain()

    def to_plain(self) -> dict:
        return {
            "calibration_worlds": sorted(self.calibration_worlds),
            "certification_worlds": sorted(self.certification_worlds),
            "evaluation_worlds": sorted(self.evaluation_worlds),
            "calibration_seeds": sorted(self.calibration_seeds),
            "certification_seeds": sorted(self.certification_seeds),
            "evaluation_seeds": sorted(self.evaluation_seeds),
            "role_manifests": {
                k: v.to_plain_with_hash() for k, v in sorted(self.role_manifests.items())
            },
            "isolated": self.validate_isolation()
                        and not (len(self.role_manifests) > 1 and self._has_overlap()),
            "frozen": self.frozen,
        }

    def _has_overlap(self) -> bool:
        names = list(self.role_manifests)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a = set(self.role_manifests[names[i]].sample_ids)
                b = set(self.role_manifests[names[j]].sample_ids)
                if a & b:
                    return True
        return False

def validate_role_isolation(
    cal_worlds, cert_worlds, eval_worlds, cal_seeds, cert_seeds, eval_seeds,
) -> bool:
    """便捷校验函数。"""
    reg = DataRoleRegistry()
    reg.calibration_worlds = set(cal_worlds)
    reg.certification_worlds = set(cert_worlds)
    reg.evaluation_worlds = set(eval_worlds)
    reg.calibration_seeds = set(cal_seeds)
    reg.certification_seeds = set(cert_seeds)
    reg.evaluation_seeds = set(eval_seeds)
    return reg.validate_isolation()


__all__ = ["DataRoleRegistry", "DataRoleManifest", "DataSplitIsolationError",
           "validate_role_isolation"]
