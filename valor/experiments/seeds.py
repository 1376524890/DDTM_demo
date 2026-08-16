"""Seed Hierarchy（EF 关键原则二）。

不能只塞 seed=42。从 master seed 派生命名空间 seed：
    S_x = H(S_master ∥ namespace_x)
使 baseline 与 Proposed 共享 world randomness，但保留 method-specific randomness。
论文才能回答：差异来自方法，而非不同随机场景。
"""

from __future__ import annotations

from valor.core.hashing import sha256_hex

# 命名空间
NS_DATASET = "dataset"
NS_SPLIT = "split"
NS_CORRUPTION = "corruption"
NS_AUDITOR_COST = "auditor_cost"
NS_OFFLINE = "offline"
NS_BYZANTINE = "byzantine"
NS_CHALLENGE = "challenge"
NS_MODEL_TRAINING = "model_training"
NS_METHOD = "method"
NS_CALIBRATION = "calibration"
NS_CERTIFICATION = "certification"
NS_EVALUATION = "evaluation"


def derive_seed(master_seed: int, namespace: str, *, salt: str = "") -> int:
    """S_x = H(S_master ∥ namespace ∥ salt)，映射到非负 int32。"""
    blob = f"{int(master_seed)}::{namespace}::{salt}".encode("utf-8")
    h = sha256_hex(blob)
    return int(h[:8], 16)  # 取前 8 hex → 32-bit


class SeedHierarchy:
    """从 master seed 派生的完整 seed 命名空间集合。"""

    def __init__(self, master_seed: int, *, salt: str = "") -> None:
        self.master_seed = int(master_seed)
        self._salt = salt

    def _d(self, ns: str) -> int:
        return derive_seed(self.master_seed, ns, salt=self._salt)

    @property
    def dataset(self) -> int:
        return self._d(NS_DATASET)

    @property
    def split(self) -> int:
        return self._d(NS_SPLIT)

    @property
    def corruption(self) -> int:
        return self._d(NS_CORRUPTION)

    @property
    def auditor_cost(self) -> int:
        return self._d(NS_AUDITOR_COST)

    @property
    def offline(self) -> int:
        return self._d(NS_OFFLINE)

    @property
    def byzantine(self) -> int:
        return self._d(NS_BYZANTINE)

    @property
    def challenge(self) -> int:
        return self._d(NS_CHALLENGE)

    @property
    def model_training(self) -> int:
        return self._d(NS_MODEL_TRAINING)

    @property
    def method(self) -> int:
        return self._d(NS_METHOD)

    @property
    def calibration(self) -> int:
        return self._d(NS_CALIBRATION)

    @property
    def certification(self) -> int:
        return self._d(NS_CERTIFICATION)

    @property
    def evaluation(self) -> int:
        return self._d(NS_EVALUATION)

    def to_plain(self) -> dict:
        return {
            "master_seed": self.master_seed,
            "salt": self._salt,
            "dataset": self.dataset,
            "split": self.split,
            "corruption": self.corruption,
            "auditor_cost": self.auditor_cost,
            "offline": self.offline,
            "byzantine": self.byzantine,
            "challenge": self.challenge,
            "model_training": self.model_training,
            "method": self.method,
            "calibration": self.calibration,
            "certification": self.certification,
            "evaluation": self.evaluation,
        }


__all__ = ["derive_seed", "SeedHierarchy", "NS_DATASET", "NS_SPLIT"]
