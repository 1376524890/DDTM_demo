"""RowChallenge —— 选择性开启挑战（方案 §10/§11）。

关键顺序：承诺 → 上架 → 绑定 → 审计动作选定 → THEN challenge。
绝不能在 seller 知道 challenge rows 之后再生成 commitment。
MVP：scheduler 生成 secrets.token_bytes(32) nonce，seed=H(taskHash∥actionID∥nonce)，
rng.choice(n_rows, k, replace=False)。
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from valor.core.hashing import content_hash, sha256_hex


@dataclass(frozen=True)
class RowChallenge:
    challenge_id: str
    task_binding_hash: str
    action_id: str
    nonce: str
    indices: tuple[int, ...]
    generated_at: str
    challenge_hash: str

    @property
    def task_hash(self) -> str:
        """Backwards-compatible alias for the pre-challenge task binding hash."""
        return self.task_binding_hash

    def to_plain(self) -> dict:
        return {
            "challenge_id": self.challenge_id,
            "task_binding_hash": self.task_binding_hash,
            "action_id": self.action_id,
            "nonce": self.nonce,
            "indices": list(self.indices),
            "generated_at": self.generated_at,
            "challenge_hash": self.challenge_hash,
        }

    @classmethod
    def from_plain(cls, d: dict) -> "RowChallenge":
        binding = d.get("task_binding_hash") or d.get("task_hash")
        if binding is None:
            raise ValueError("RowChallenge requires task_binding_hash")
        return cls(
            challenge_id=d["challenge_id"], task_binding_hash=binding,
            action_id=d["action_id"], nonce=d["nonce"],
            indices=tuple(d["indices"]), generated_at=d["generated_at"],
            challenge_hash=d["challenge_hash"],
        )


def generate_challenge(
    *,
    task_hash: str,
    task_binding_hash: str | None = None,
    action_id: str,
    n_rows: int,
    k: int,
    nonce: bytes | None = None,
) -> RowChallenge:
    """生成全局挑战（所有 committee auditor 验证同一批 openings）。

    seed = H(taskBindingHash ∥ actionID ∥ challengeNonce)
    """
    if k > n_rows:
        raise ValueError(f"k={k} > n_rows={n_rows}")
    binding = task_binding_hash or task_hash
    nonce = nonce or secrets.token_bytes(32)
    seed_hex = sha256_hex(
        content_hash({
            "taskBindingHash": binding, "actionID": action_id,
            "challengeNonce": nonce.hex(),
        }).encode())
    seed = int(seed_hex[:8], 16)
    rng = np.random.default_rng(seed)
    indices = tuple(sorted(int(i) for i in rng.choice(n_rows, size=k, replace=False)))
    challenge_id = f"challenge-{sha256_hex(seed_hex.encode())[:12]}"
    generated_at = datetime.now(timezone.utc).isoformat()
    challenge_hash = sha256_hex(content_hash({
        "challenge_id": challenge_id, "task_binding_hash": binding,
        "action_id": action_id, "nonce": nonce.hex(), "indices": list(indices),
        "generated_at": generated_at,
    }).encode())
    return RowChallenge(
        challenge_id=challenge_id, task_binding_hash=binding, action_id=action_id,
        nonce=nonce.hex(), indices=indices, generated_at=generated_at,
        challenge_hash=challenge_hash,
    )


def validate_challenge_indices(challenge: RowChallenge, n_rows: int) -> bool:
    """校验 indices：唯一、0<=i<N、len=k。"""
    idx = challenge.indices
    return (
        len(set(idx)) == len(idx)
        and all(0 <= i < n_rows for i in idx)
        and len(idx) == len(set(idx))
    )


__all__ = ["RowChallenge", "generate_challenge", "validate_challenge_indices"]
