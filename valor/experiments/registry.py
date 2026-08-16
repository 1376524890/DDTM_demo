"""R_cal / R_cert / R_eval 三集合隔离（EF-G03）。

强制：R_cal ∩ R_cert = R_cal ∩ R_eval = R_cert ∩ R_eval = ∅。
    - likelihood 从 R_cal 得
    - p̲_B^sys certificate 从 R_cert 得
    - RQ metrics 从 R_eval 得
正式论文结果只能来自 R_eval。
"""

from __future__ import annotations

from dataclasses import dataclass, field


class DataSplitIsolationError(Exception):
    """三集合交叉 → 隔离失败。"""


@dataclass
class DataRoleRegistry:
    """数据角色注册表：world_id / dataset indices / seeds 三集合隔离。"""

    calibration_worlds: set[str] = field(default_factory=set)
    certification_worlds: set[str] = field(default_factory=set)
    evaluation_worlds: set[str] = field(default_factory=set)
    calibration_seeds: set[int] = field(default_factory=set)
    certification_seeds: set[int] = field(default_factory=set)
    evaluation_seeds: set[int] = field(default_factory=set)

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

    def to_plain(self) -> dict:
        return {
            "calibration_worlds": sorted(self.calibration_worlds),
            "certification_worlds": sorted(self.certification_worlds),
            "evaluation_worlds": sorted(self.evaluation_worlds),
            "calibration_seeds": sorted(self.calibration_seeds),
            "certification_seeds": sorted(self.certification_seeds),
            "evaluation_seeds": sorted(self.evaluation_seeds),
            "isolated": self.validate_isolation(),
        }


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


__all__ = ["DataRoleRegistry", "DataSplitIsolationError", "validate_role_isolation"]
