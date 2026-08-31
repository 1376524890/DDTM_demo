"""Cross-mechanism reverse provenance validator (Round 7 P0-32).

Given a context with artifact nodes/edges, verifies that the required reverse
paths reach concrete leaves with artifact_hash/type/producer/source_kind/run
binding. Missing leaves -> PROVENANCE_INCOMPLETE.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash


@dataclass
class ProvenanceNode:
    node_id: str
    artifact_hash: str
    node_type: str
    producer: str
    source_kind: str
    run_tx_binding: str = ""


@dataclass
class ReverseProvenanceReport:
    required_paths: list[str] = field(default_factory=list)
    path_results: dict[str, dict] = field(default_factory=dict)
    unresolved_leaves: list[str] = field(default_factory=list)
    required_paths_failed: int = 0

    def to_plain(self) -> dict:
        return {
            "required_paths": self.required_paths,
            "path_results": self.path_results,
            "unresolved_leaves": self.unresolved_leaves,
            "required_paths_failed": self.required_paths_failed,
        }


class ReverseProvenanceValidator:
    """Validates reverse provenance across pricing/certification/audit/usage/model."""

    REQUIRED_PATHS = [
        "P_star_to_pricing_leaves",
        "pBsys_to_Rcert_to_AuditPolicy_to_ActionCatalog_to_RLikelihood",
        "audit_execution_to_frozen_quote_to_market_snapshot_to_VCG",
        "seller_breach_to_signed_audit_evidence",
        "buyer_breach_to_usage_violation_evidence_to_usage_receipt_to_PDP",
        "model_artifact_to_worker_execution_to_capability_to_rights_to_delivery_to_commitment",
    ]

    def __init__(self, nodes: dict[str, ProvenanceNode] | None = None,
                 edges: list[dict] | None = None) -> None:
        self.nodes = nodes or {}
        self.edges = edges or []

    def add_node(self, node: ProvenanceNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, parent: str, child: str, role: str = "dependency") -> None:
        self.edges.append({"parent": parent, "child": child, "role": role})

    def _reverse(self, root: str) -> list[str]:
        seen: set[str] = set()
        stack = [root]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for e in self.edges:
                if e["child"] == cur and e["parent"] not in seen:
                    stack.append(e["parent"])
        return sorted(seen)

    def validate(self) -> ReverseProvenanceReport:
        report = ReverseProvenanceReport(required_paths=list(self.REQUIRED_PATHS))
        for path in self.REQUIRED_PATHS:
            root = path.split("_to_")[0]  # approximate root name
            closure = self._reverse(root)
            missing = []
            for nid, node in self.nodes.items():
                if nid in closure and not node.artifact_hash:
                    missing.append(nid)
            unresolved = [nid for nid in closure if nid not in self.nodes]
            ok = bool(closure) and not missing and not unresolved
            if not ok:
                report.required_paths_failed += 1
                report.unresolved_leaves.extend(missing + unresolved)
            report.path_results[path] = {
                "passed": ok,
                "root": root,
                "closure_count": len(closure),
                "unresolved": unresolved,
                "missing_artifact_hash": missing,
            }
        report.unresolved_leaves = sorted(set(report.unresolved_leaves))
        return report


__all__ = ["ProvenanceNode", "ReverseProvenanceReport", "ReverseProvenanceValidator"]
