"""PricingProvenanceGraph (Round 6 Phase 16) — DAG over pricing dependencies.

Each node is a semantic pricing parameter; each edge says `parent` is required
to compute `child`. The root is P* (clearing price). `reverse("P_star")`
returns the full dependency closure. Unresolved leaves are marked
PRICING_PROVENANCE_INCOMPLETE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash


@dataclass(frozen=True)
class ResolvedParameter:
    """A pricing provenance node (kept source-compatible with Round 5)."""

    name: str
    value: Any
    source: str  # CONTRACT_INPUT | CALIBRATION | CERTIFIED | MARKET | AUDIT | COMPUTED
    source_ref: str = ""
    formula_id: str = ""
    node_id: str = ""
    unit: str = ""
    source_artifact_hash: str = ""

    def __post_init__(self) -> None:
        if not self.node_id:
            object.__setattr__(self, "node_id", self.name)
        if not self.source_artifact_hash:
            object.__setattr__(self, "source_artifact_hash", self.source_ref)

    @property
    def semantic_name(self) -> str:
        return self.name

    @property
    def source_kind(self) -> str:
        return self.source

    def to_plain(self) -> dict:
        return {
            "node_id": self.node_id,
            "semantic_name": self.semantic_name,
            "value": self.value,
            "unit": self.unit,
            "source_kind": self.source_kind,
            "source_artifact_hash": self.source_artifact_hash,
            "formula_id": self.formula_id,
            "source_ref": self.source_ref,
        }


@dataclass
class PricingProvenanceGraph:
    """Directed graph of pricing dependencies rooted at P*."""

    nodes: dict[str, ResolvedParameter] = field(default_factory=dict)
    edges: list[dict] = field(default_factory=list)
    root: str = "P_star"
    # backward-compatible flat view
    parameters: list[ResolvedParameter] = field(default_factory=list)

    def add(self, param: ResolvedParameter) -> None:
        self.nodes[param.node_id] = param
        self.parameters.append(param)

    def add_many(self, params: list[ResolvedParameter]) -> None:
        for p in params:
            self.add(p)

    def add_edge(self, parent: str, child: str, role: str = "dependency") -> None:
        if parent not in self.nodes or child not in self.nodes:
            raise KeyError(f"PRICING_PROVENANCE_INCOMPLETE: {parent}->{child}")
        self.edges.append({"parent": parent, "child": child, "role": role})

    def reverse(self, node_id: str) -> list[str]:
        """Return the dependency closure of node_id (parents recursively)."""
        seen: set[str] = set()
        stack = [node_id]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for e in self.edges:
                if e["child"] == cur and e["parent"] not in seen:
                    stack.append(e["parent"])
        return sorted(seen)

    def unresolved_leaves(self) -> list[str]:
        leaves = [nid for nid, node in self.nodes.items()
                  if node.source_kind not in {
                      "CONTRACT_INPUT", "CALIBRATION", "MARKET_DISCOVERED",
                      "CERTIFIED", "OBSERVED_DATA"}]
        return leaves

    def graph_hash(self) -> str:
        return content_hash({
            "nodes": {k: v.to_plain() for k, v in sorted(self.nodes.items())},
            "edges": sorted([(e["parent"], e["child"], e["role"]) for e in self.edges]),
            "root": self.root,
        })

    def to_plain(self) -> dict:
        return {
            "nodes": [n.to_plain() for n in self.nodes.values()],
            "edges": self.edges,
            "root": self.root,
            "reverse_P_star": self.reverse(self.root),
            "unresolved_leaves": self.unresolved_leaves(),
            "graph_hash": self.graph_hash(),
            # keep flat parameters for backward compatibility
            "parameters": [p.to_plain() for p in self.parameters],
        }


__all__ = ["ResolvedParameter", "PricingProvenanceGraph"]
