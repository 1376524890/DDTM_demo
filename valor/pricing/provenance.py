"""PricingProvenanceGraph (Round 5 §21)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash


@dataclass(frozen=True)
class ResolvedParameter:
    name: str
    value: Any
    source: str  # CONTRACT_INPUT | CALIBRATION | CERTIFIED | MARKET | AUDIT | COMPUTED
    source_ref: str = ""
    formula_id: str = ""

    def to_plain(self) -> dict:
        return {
            "name": self.name, "value": self.value,
            "source": self.source, "source_ref": self.source_ref,
            "formula_id": self.formula_id,
        }


@dataclass
class PricingProvenanceGraph:
    parameters: list[ResolvedParameter] = field(default_factory=list)

    def add(self, param: ResolvedParameter) -> None:
        self.parameters.append(param)

    def add_many(self, params: list[ResolvedParameter]) -> None:
        self.parameters.extend(params)

    def graph_hash(self) -> str:
        return content_hash([p.to_plain() for p in self.parameters])

    def to_plain(self) -> dict:
        return {
            "parameters": [p.to_plain() for p in self.parameters],
            "graph_hash": self.graph_hash(),
        }


__all__ = ["ResolvedParameter", "PricingProvenanceGraph"]
