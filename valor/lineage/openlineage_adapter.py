"""OpenLineage 兼容导出（规范 §33 / MFC-G36）。

VALOR 权威血缘是 hash-chain；本模块只做 OpenLineage-compatible 导出：
    DataAsset → Dataset
    TrainingJobSpec → Job
    job execution → Run
    Usage event → RunEvent

custom facets 携带 tx_id / rights_hash / purpose / decision / dataset_commitment /
attestation_ref / usage_receipt_hash。不另造第二套 mechanism。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash
from valor.lineage.models import DataFlowEvent


@dataclass
class OpenLineageExport:
    """一次 OpenLineage 兼容导出结果。"""

    dataset_events: list[dict] = field(default_factory=list)
    job_events: list[dict] = field(default_factory=list)
    run_events: list[dict] = field(default_factory=list)

    def add_dataset(self, *, name: str, namespace: str, facets: dict) -> None:
        self.dataset_events.append({
            "eventType": "DATASET",
            "eventTime": "2026-01-01T00:00:00+00:00",
            "producer": "https://github.com/valor",
            "schemaURL": "https://openlineage.io/spec/1-0-5",
            "dataset": {"name": name, "namespace": namespace, "facets": facets},
        })

    def add_job(self, *, name: str, namespace: str, facets: dict) -> None:
        self.job_events.append({
            "eventType": "RUN_START",
            "job": {"name": name, "namespace": namespace, "facets": facets},
        })

    def add_run_event(self, *, run_id: str, job_name: str, namespace: str,
                      facets: dict) -> None:
        self.run_events.append({
            "eventType": "COMPLETE",
            "run": {"runId": run_id, "facets": facets},
            "job": {"name": job_name, "namespace": namespace},
            "inputs": [], "outputs": [],
        })

    def to_plain(self) -> dict:
        return {
            "dataset_events": self.dataset_events,
            "job_events": self.job_events,
            "run_events": self.run_events,
        }


def export_usage_events(events: list[DataFlowEvent]) -> OpenLineageExport:
    """把 VALOR lineage 事件导出为 OpenLineage RunEvents。"""
    out = OpenLineageExport()
    for e in events:
        out.add_run_event(
            run_id=e.event_id, job_name=f"valor-{e.action.lower()}",
            namespace=f"valor:{e.tx_id}",
            facets={
                "tx_id": e.tx_id, "rights_hash": e.rights_ref,
                "purpose": e.purpose, "decision": e.evidence,
                "env": e.env, "actor": e.actor,
                "dataset_commitment": list(e.input_refs)[0] if e.input_refs else "",
            })
    return out


def export_training_job(job_spec, *, run_id: str) -> OpenLineageExport:
    """把 TrainingJobSpec 导出为 OpenLineage Job + Run。"""
    out = OpenLineageExport()
    out.add_job(
        name=job_spec.algorithm_id, namespace=f"valor:train:{job_spec.tx_id}",
        facets={"job_spec_hash": job_spec.job_spec_hash,
                "algorithm_hash": job_spec.algorithm_hash,
                "dataset_commitment": job_spec.dataset_commitment_hash,
                "rights_hash": job_spec.rights_hash, "purpose": job_spec.declared_purpose})
    out.add_run_event(
        run_id=run_id, job_name=job_spec.algorithm_id,
        namespace=f"valor:train:{job_spec.tx_id}",
        facets={"tx_id": job_spec.tx_id, "rights_hash": job_spec.rights_hash,
                "dataset_commitment": job_spec.dataset_commitment_hash,
                "purpose": job_spec.declared_purpose,
                "job_spec_hash": job_spec.job_spec_hash})
    return out


__all__ = ["OpenLineageExport", "export_usage_events", "export_training_job"]
