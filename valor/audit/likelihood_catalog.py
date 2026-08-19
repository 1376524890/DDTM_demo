"""FrozenLikelihoodArtifact + LikelihoodCatalog (Round 4 P0-C)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash


@dataclass(frozen=True)
class FrozenLikelihoodArtifact:
    action_profile_hash: str
    action_id: str
    calibration_role_hash: str
    outcome_vocabulary_version: str
    counts: dict[str, dict[str, int]]
    dirichlet_prior: dict[str, float]
    likelihood_rows: dict[str, dict[str, float]]
    calibration_code_hash: str
    raw_event_refs: list[str]
    artifact_hash: str = ""

    def __post_init__(self) -> None:
        if not self.artifact_hash:
            object.__setattr__(self, "artifact_hash", content_hash({
                "action_profile_hash": self.action_profile_hash,
                "action_id": self.action_id,
                "calibration_role_hash": self.calibration_role_hash,
                "outcome_vocabulary_version": self.outcome_vocabulary_version,
                "counts": self.counts,
                "dirichlet_prior": self.dirichlet_prior,
                "likelihood_rows": self.likelihood_rows,
                "calibration_code_hash": self.calibration_code_hash,
                "raw_event_refs": self.raw_event_refs,
            }))

    def to_plain(self) -> dict:
        return {
            "action_profile_hash": self.action_profile_hash,
            "action_id": self.action_id,
            "calibration_role_hash": self.calibration_role_hash,
            "outcome_vocabulary_version": self.outcome_vocabulary_version,
            "counts": self.counts,
            "dirichlet_prior": self.dirichlet_prior,
            "likelihood_rows": self.likelihood_rows,
            "calibration_code_hash": self.calibration_code_hash,
            "raw_event_refs": self.raw_event_refs,
            "artifact_hash": self.artifact_hash,
        }


class LikelihoodCatalog:
    """Profile-hash -> frozen likelihood artifact registry."""

    def __init__(self) -> None:
        self._artifacts: dict[str, FrozenLikelihoodArtifact] = {}

    def register(self, artifact: FrozenLikelihoodArtifact) -> None:
        self._artifacts[artifact.action_profile_hash] = artifact

    def resolve(self, action_profile_hash: str) -> FrozenLikelihoodArtifact:
        if action_profile_hash not in self._artifacts:
            raise KeyError(
                f"ACTION_NOT_CERTIFIED: no likelihood artifact for profile "
                f"{action_profile_hash}"
            )
        return self._artifacts[action_profile_hash]

    def catalog_hash(self) -> str:
        return content_hash({
            k: v.artifact_hash
            for k, v in sorted(self._artifacts.items())
        })

    def to_plain(self) -> dict:
        return {
            "catalog_hash": self.catalog_hash(),
            "artifacts": {k: v.to_plain() for k, v in self._artifacts.items()},
        }


__all__ = ["FrozenLikelihoodArtifact", "LikelihoodCatalog"]
