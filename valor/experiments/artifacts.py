"""Immutable Raw Artifacts（EF-G05/G08/G15）。

trial 完成后 immutable=true。重跑相同 trial_id：
    - hash 一致 → skip
    - hash 不一致 → REPRODUCIBILITY_VIOLATION（禁止静默覆盖）

manifest 绑定 git/config/data/calibration/cert/execution_mode。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from valor.core.hashing import content_hash

# 错误码
REPRODUCIBILITY_VIOLATION = "REPRODUCIBILITY_VIOLATION"


class ArtifactStore:
    """immutable trial artifact 存储。"""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _trial_dir(self, trial_id: str) -> Path:
        d = self.root / "trials" / trial_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _immutable_marker(self, trial_dir: Path) -> Path:
        return trial_dir / ".immutable"

    def exists(self, trial_id: str) -> bool:
        return (self._trial_dir(trial_id) / "result.json").exists()

    def is_immutable(self, trial_id: str) -> bool:
        return self._immutable_marker(self._trial_dir(trial_id)).exists()

    def write_trial(
        self, trial_id: str, *, result: dict, manifest: dict,
    ) -> tuple[str, bool]:
        """写入 trial；若已 immutable 且 hash 一致 → skip(True)；不一致 → 抛错。"""
        td = self._trial_dir(trial_id)
        if self.is_immutable(trial_id):
            prev_hash = self._read_hash(td / "result.json")
            new_hash = content_hash({"result": result, "manifest": manifest})
            if prev_hash == new_hash:
                return prev_hash, True  # 一致 → skip
            raise ArtifactReproducibilityViolation(
                f"trial {trial_id} 已 immutable 但 hash 不一致"
                f"（{prev_hash[:12]} != {new_hash[:12]}）")
        # 首次写入
        manifest["_trial_id"] = trial_id
        result_hash = content_hash({"result": result, "manifest": manifest})
        manifest["result_hash"] = result_hash
        (td / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (td / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (td / "result_hash.txt").write_text(result_hash, encoding="utf-8")
        self._immutable_marker(td).write_text("immutable", encoding="utf-8")
        return result_hash, False

    def read_result(self, trial_id: str) -> dict:
        p = self._trial_dir(trial_id) / "result.json"
        return json.loads(p.read_text(encoding="utf-8"))

    def read_manifest(self, trial_id: str) -> dict:
        p = self._trial_dir(trial_id) / "manifest.json"
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def _read_hash(p: Path) -> str:
        return p.read_text(encoding="utf-8").strip()


class ArtifactReproducibilityViolation(Exception):
    """重跑 hash 不一致 → REPRODUCIBILITY_VIOLATION。"""

    code = REPRODUCIBILITY_VIOLATION


def build_manifest(
    *, experiment_id: str, trial_id: str, method_id: str, world_id: str,
    git_commit: str, config_hash: str, dataset_hash: str, split_hash: str,
    calibration_artifact_hash: str, certificate_hash: str, execution_mode: str,
    seed: int,
) -> dict:
    """EF-G08：manifest 绑定 git/config/data/calibration/cert/execution_mode。"""
    return {
        "experiment_id": experiment_id,
        "trial_id": trial_id,
        "method_id": method_id,
        "world_id": world_id,
        "git_commit": git_commit,
        "config_hash": config_hash,
        "dataset_hash": dataset_hash,
        "split_hash": split_hash,
        "calibration_artifact_hash": calibration_artifact_hash,
        "certificate_hash": certificate_hash,
        "execution_mode": execution_mode,
        "seed": seed,
    }


def artifact_root_hash(root: str | Path) -> str:
    """EF-G08/G15：对整个 artifact 目录做确定性 hash。"""
    import os

    root = Path(root)
    entries = sorted(p.relative_to(root).as_posix()
                     for p in root.rglob("*") if p.is_file())
    blobs = []
    for rel in entries:
        p = root / rel
        blobs.append(rel)
        blobs.append(p.read_bytes().hex())
    return content_hash(blobs)


__all__ = [
    "ArtifactStore", "ArtifactReproducibilityViolation",
    "REPRODUCIBILITY_VIOLATION", "build_manifest", "artifact_root_hash",
]
