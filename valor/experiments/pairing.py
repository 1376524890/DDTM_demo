"""Paired Design（EF-G01）。

生成 paired trial 计划：对每个 world，所有 method 在**同一 world** 上运行。
baseline 与 Proposed 共享 world randomness；只差 method 策略。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .spec import ExperimentSpec, TrialSpec, WorldSpec


@dataclass
class PairedPlan:
    """一个 paired 实验计划。"""

    experiment: ExperimentSpec
    worlds: list[WorldSpec] = field(default_factory=list)
    # method_id -> {method_config}
    method_configs: dict[str, dict] = field(default_factory=dict)

    def add_world(self, world: WorldSpec) -> None:
        self.worlds.append(world)

    def add_method_config(self, method_id: str, config: dict) -> None:
        self.method_configs[method_id] = config

    def trials(self) -> list[TrialSpec]:
        """为每个 world × method 生成 TrialSpec（同一 world 复用）。"""
        out = []
        for w in self.worlds:
            for m in self.experiment.methods:
                cfg = self.method_configs.get(m, {})
                out.append(TrialSpec.build(
                    experiment_id=self.experiment.experiment_id,
                    world=w, method_id=m, method_config=cfg))
        return out

    def trials_for_world(self, world: WorldSpec) -> list[TrialSpec]:
        return [t for t in self.trials() if t.world.world_id == world.world_id]

    def methods_share_world(self) -> bool:
        """EF-G01：每个 world 的所有 method 共享同一 world（paired）。"""
        if not self.experiment.paired:
            return True
        for w in self.worlds:
            ts = self.trials_for_world(w)
            worlds = {t.world.world_hash for t in ts}
            if len(worlds) != 1:
                return False
        return True


def build_paired_plan(
    *,
    experiment: ExperimentSpec,
    world_factory,
    method_configs: dict[str, dict],
) -> PairedPlan:
    """从 world_factory(seed, world_id) 生成 worlds，构建 paired plan。"""
    plan = PairedPlan(experiment=experiment)
    for i, seed in enumerate(experiment.seeds):
        world = world_factory(seed, world_id=f"world-{i + 1:06d}")
        plan.add_world(world)
    for m, cfg in method_configs.items():
        plan.add_method_config(m, cfg)
    return plan


__all__ = ["PairedPlan", "build_paired_plan"]
