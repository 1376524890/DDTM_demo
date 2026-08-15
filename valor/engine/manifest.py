"""RunManifest —— 冻结单次 run 的全部可复现性信息（P0 基础设施）。

对齐交接文档要求：一次 MNIST 成交价必须能唯一映射到
    commit / config / dataset / split / calibration / certificate / seed
否则该数值不能进入论文。

RunManifest 由各阶段逐步填充（freeze 前可补字段），freeze() 后不可变，
并输出确定性 manifest hash。所有字段必须来自上游 artifact / 显式参数，
禁止从 config 重新手填同一个量。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import hash_object
from valor.core.reproducibility import (
    build_repro_metadata,
    dependency_lock_hash,
    git_commit,
    git_dirty,
)
from valor.core.ids import TransactionID


@dataclass
class RunManifest:
    """单次 run 的可复现性冻结清单。

    未冻结字段为 None；freeze() 后所有 required 字段必须非空（fail closed），
    否则抛 ValueError。hash = H(Canonicalize(冻结后字段))。
    """

    run_id: str | None = None
    tx_id: str | None = None
    config_hash: str | None = None
    dataset_hash: str | None = None
    split_hash: str | None = None
    parameter_manifest_hash: str | None = None
    trainer_hash: str | None = None
    model_config_hash: str | None = None
    dependency_lock_hash: str | None = None
    valuation_calibration_hash: str | None = None
    action_catalog_hash: str | None = None
    audit_policy_hash: str | None = None
    certificate_hash: str | None = None
    seed: int | None = None
    # 自动填充（冻结时）
    git_commit: str | None = None
    git_dirty: bool | None = None
    python_version: str | None = None
    platform: str | None = None
    valor_version: str | None = None
    hardware: str | None = None
    timestamp_utc: str | None = None
    _frozen: bool = field(default=False, init=False, repr=False)

    _REQUIRED = (
        "run_id", "tx_id", "config_hash", "dataset_hash", "split_hash",
        "parameter_manifest_hash", "trainer_hash", "model_config_hash",
        "dependency_lock_hash", "valuation_calibration_hash",
        "action_catalog_hash", "audit_policy_hash", "certificate_hash",
        "seed",
    )

    def set(self, **kwargs: Any) -> "RunManifest":
        """冻结前填充字段（幂等，可链式）。冻结后抛错。"""
        if self._frozen:
            raise ValueError("manifest 已冻结，不可修改")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                raise ValueError(f"manifest 无字段 {k!r}")
            setattr(self, k, v)
        return self

    def freeze(
        self,
        *,
        repo_root: str = ".",
        run_id: str | None = None,
        tx_id: str | None = None,
        seed: int | None = None,
    ) -> "RunManifest":
        """冻结：校验 required 齐全，自动填充环境/版本元数据，返回自身。"""
        if run_id is not None:
            self.run_id = run_id
        if tx_id is not None:
            self.tx_id = tx_id
        if seed is not None:
            self.seed = seed
        missing = [k for k in self._REQUIRED if getattr(self, k) is None]
        if missing:
            raise ValueError(f"manifest 冻结失败，缺 required 字段: {missing}")

        repro = build_repro_metadata(config_hash=self.config_hash, repo_root=repo_root)
        self.git_commit = repro["git_commit"]
        self.git_dirty = repro["git_dirty"]
        self.python_version = repro["python_version"]
        self.platform = repro["platform"]
        self.valor_version = repro["valor_version"]
        self.hardware = _hardware()
        self.timestamp_utc = repro["timestamp_utc"]
        if self.dependency_lock_hash is None:
            self.dependency_lock_hash = dependency_lock_hash()
        self._frozen = True
        return self

    def _plain_without_hash(self) -> dict[str, Any]:
        """不含 manifest_hash 的字段表示（供计算 hash，避免递归）。"""
        return {
            "run_id": self.run_id,
            "tx_id": self.tx_id,
            "config_hash": self.config_hash,
            "dataset_hash": self.dataset_hash,
            "split_hash": self.split_hash,
            "parameter_manifest_hash": self.parameter_manifest_hash,
            "trainer_hash": self.trainer_hash,
            "model_config_hash": self.model_config_hash,
            "dependency_lock_hash": self.dependency_lock_hash,
            "valuation_calibration_hash": self.valuation_calibration_hash,
            "action_catalog_hash": self.action_catalog_hash,
            "audit_policy_hash": self.audit_policy_hash,
            "certificate_hash": self.certificate_hash,
            "seed": self.seed,
            "git_commit": self.git_commit,
            "git_dirty": self.git_dirty,
            "python_version": self.python_version,
            "platform": self.platform,
            "valor_version": self.valor_version,
            "hardware": self.hardware,
            "timestamp_utc": self.timestamp_utc,
        }

    @property
    def manifest_hash(self) -> str:
        """确定性 manifest 哈希（冻结后可计算）。"""
        return hash_object(self._plain_without_hash())

    def to_plain(self) -> dict[str, Any]:
        """JSON 原生表示（含 hash）。"""
        d = self._plain_without_hash()
        d["manifest_hash"] = self.manifest_hash if self._frozen else None
        d["frozen"] = self._frozen
        return d

    @classmethod
    def from_plain(cls, d: dict[str, Any]) -> "RunManifest":
        """从 to_plain 结果重建（round-trip）。"""
        m = cls()
        for k in list(cls._REQUIRED) + [
            "run_id", "tx_id", "git_commit", "git_dirty", "python_version",
            "platform", "valor_version", "hardware", "timestamp_utc",
        ]:
            if d.get(k) is not None:
                setattr(m, k, d[k])
        m._frozen = bool(d.get("frozen"))
        return m


def _hardware() -> str:
    """读取硬件描述（尽力而为，失败返回 unknown）。"""
    try:
        import platform as _p

        return _p.machine()
    except Exception:
        return "unknown"


def default_manifest(
    *,
    run_id: str,
    tx_id: str,
    config_hash: str,
    dataset_hash: str,
    seed: int,
    split_hash: str | None = None,
) -> RunManifest:
    """便捷构造：填入 run/tx 标识与最核心的冻结哈希，其余后续 set()。"""
    return RunManifest().set(
        run_id=run_id,
        tx_id=tx_id,
        config_hash=config_hash,
        dataset_hash=dataset_hash,
        split_hash=split_hash,
        seed=seed,
    )


__all__ = ["RunManifest", "default_manifest"]
