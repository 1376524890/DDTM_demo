"""TraceLedger —— 统一 hash-chain 事件账本（P0 基础设施）。

对齐交接文档要求：所有阶段都写统一结构，形成 transaction_trace.jsonl，
且该文件本身是 hash chain：

    H_i = H(H_{i-1} ∥ Canonical(Event_i))

每个 event 记录：stage / event_type / state_before / state_after / formula_id /
formula_inputs / formula_output / parameter_refs / evidence_refs / algorithm_id /
algorithm_hash / dataset_hash / config_hash / seed / duration_ms / prev_event_hash /
event_hash。

原则（P0 核心）：
- 下游只能读取上游 event 的 formula_output / evidence_refs，禁止从 config 重填。
- 追加即校验 prev hash（防止篡改）；verify() 可整体重放校验。
- 事件只存 leaf 字段（不序列化活对象）；formula_inputs/output 必须是可 canonicalize 的原生结构。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from valor.core.canonical_json import canonicalize
from valor.core.hashing import sha256_hex, stable_hash


def _event_hash(seq: int, prev_hash: str | None, body: dict[str, Any]) -> str:
    """H_i = H(seq ∥ prev_hash ∥ Canonical(body))。"""
    parts = [seq]
    if prev_hash:
        parts.append(prev_hash)
    parts.append(canonicalize(body))
    return stable_hash(*parts)


@dataclass
class TraceEvent:
    """一条 trace 事件（叶子字段，可 canonicalize）。"""

    seq: int
    stage: str
    event_type: str
    run_id: str
    tx_id: str
    config_hash: str
    dataset_hash: str
    seed: int
    formula_id: str | None = None
    formula_inputs: dict[str, Any] = field(default_factory=dict)
    formula_output: dict[str, Any] = field(default_factory=dict)
    state_before: str | None = None
    state_after: str | None = None
    parameter_refs: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    algorithm_id: str | None = None
    algorithm_hash: str | None = None
    duration_ms: float | None = None
    prev_event_hash: str | None = None
    event_hash: str = ""

    def compute_hash(self) -> str:
        body = {
            "seq": self.seq,
            "stage": self.stage,
            "event_type": self.event_type,
            "run_id": self.run_id,
            "tx_id": self.tx_id,
            "config_hash": self.config_hash,
            "dataset_hash": self.dataset_hash,
            "seed": self.seed,
            "formula_id": self.formula_id,
            "formula_inputs": self.formula_inputs,
            "formula_output": self.formula_output,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "parameter_refs": self.parameter_refs,
            "evidence_refs": self.evidence_refs,
            "algorithm_id": self.algorithm_id,
            "algorithm_hash": self.algorithm_hash,
            "duration_ms": self.duration_ms,
        }
        return _event_hash(self.seq, self.prev_event_hash, body)

    def to_plain(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "stage": self.stage,
            "event_type": self.event_type,
            "run_id": self.run_id,
            "tx_id": self.tx_id,
            "config_hash": self.config_hash,
            "dataset_hash": self.dataset_hash,
            "seed": self.seed,
            "formula_id": self.formula_id,
            "formula_inputs": self.formula_inputs,
            "formula_output": self.formula_output,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "parameter_refs": self.parameter_refs,
            "evidence_refs": self.evidence_refs,
            "algorithm_id": self.algorithm_id,
            "algorithm_hash": self.algorithm_hash,
            "duration_ms": self.duration_ms,
            "prev_event_hash": self.prev_event_hash,
            "event_hash": self.event_hash,
        }

    @classmethod
    def from_plain(cls, d: dict[str, Any]) -> "TraceEvent":
        return cls(
            seq=d["seq"], stage=d["stage"], event_type=d["event_type"],
            run_id=d["run_id"], tx_id=d["tx_id"],
            config_hash=d["config_hash"], dataset_hash=d["dataset_hash"],
            seed=d["seed"], formula_id=d.get("formula_id"),
            formula_inputs=d.get("formula_inputs", {}),
            formula_output=d.get("formula_output", {}),
            state_before=d.get("state_before"), state_after=d.get("state_after"),
            parameter_refs=d.get("parameter_refs", []),
            evidence_refs=d.get("evidence_refs", []),
            algorithm_id=d.get("algorithm_id"), algorithm_hash=d.get("algorithm_hash"),
            duration_ms=d.get("duration_ms"),
            prev_event_hash=d.get("prev_event_hash"),
            event_hash=d.get("event_hash", ""),
        )


class TraceLedger:
    """追加式 hash-chain 账本。append 校验 prev hash；verify() 全链重放。"""

    def __init__(
        self,
        *,
        run_id: str,
        tx_id: str,
        config_hash: str,
        dataset_hash: str,
        seed: int,
    ) -> None:
        self.run_id = run_id
        self.tx_id = tx_id
        self.config_hash = config_hash
        self.dataset_hash = dataset_hash
        self.seed = seed
        self._events: list[TraceEvent] = []
        self._last_hash: str | None = None

    @property
    def last_hash(self) -> str | None:
        return self._last_hash

    @property
    def events(self) -> list[TraceEvent]:
        return list(self._events)

    def append(
        self,
        *,
        stage: str,
        event_type: str,
        formula_id: str | None = None,
        formula_inputs: dict[str, Any] | None = None,
        formula_output: dict[str, Any] | None = None,
        state_before: str | None = None,
        state_after: str | None = None,
        parameter_refs: list[str] | None = None,
        evidence_refs: list[str] | None = None,
        algorithm_id: str | None = None,
        algorithm_hash: str | None = None,
        duration_ms: float | None = None,
    ) -> TraceEvent:
        """追加一条事件；返回已哈希的 TraceEvent。"""
        seq = len(self._events) + 1
        ev = TraceEvent(
            seq=seq, stage=stage, event_type=event_type,
            run_id=self.run_id, tx_id=self.tx_id,
            config_hash=self.config_hash, dataset_hash=self.dataset_hash,
            seed=self.seed, formula_id=formula_id,
            formula_inputs=formula_inputs or {},
            formula_output=formula_output or {},
            state_before=state_before, state_after=state_after,
            parameter_refs=parameter_refs or [],
            evidence_refs=evidence_refs or [],
            algorithm_id=algorithm_id, algorithm_hash=algorithm_hash,
            duration_ms=duration_ms, prev_event_hash=self._last_hash,
        )
        ev.event_hash = ev.compute_hash()
        self._events.append(ev)
        self._last_hash = ev.event_hash
        return ev

    def append_measured(self, fn, **kwargs) -> tuple[TraceEvent, Any]:
        """执行 fn 并计时，把时长写入事件。fn 返回的值作为 formula_output 兜底。"""
        t0 = time.perf_counter()
        out = fn()
        dt_ms = (time.perf_counter() - t0) * 1000.0
        kwargs.setdefault("formula_output", {})["__duration_ms"] = dt_ms
        ev = self.append(duration_ms=dt_ms, **kwargs)
        return ev, out

    def to_plain(self) -> list[dict[str, Any]]:
        return [e.to_plain() for e in self._events]

    def to_jsonl(self) -> str:
        import json

        return "\n".join(json.dumps(e.to_plain(), ensure_ascii=False) for e in self._events)

    def verify(self) -> tuple[bool, str | None]:
        """重放校验 hash chain；返回 (ok, 出错 seq 或 None)。"""
        prev: str | None = None
        for ev in self._events:
            if ev.prev_event_hash != prev:
                return False, ev.seq
            expect = _event_hash(
                ev.seq, prev,
                canonicalize({
                    "seq": ev.seq, "stage": ev.stage, "event_type": ev.event_type,
                    "run_id": ev.run_id, "tx_id": ev.tx_id,
                    "config_hash": ev.config_hash, "dataset_hash": ev.dataset_hash,
                    "seed": ev.seed, "formula_id": ev.formula_id,
                    "formula_inputs": ev.formula_inputs,
                    "formula_output": ev.formula_output,
                    "state_before": ev.state_before, "state_after": ev.state_after,
                    "parameter_refs": ev.parameter_refs,
                    "evidence_refs": ev.evidence_refs,
                    "algorithm_id": ev.algorithm_id,
                    "algorithm_hash": ev.algorithm_hash,
                    "duration_ms": ev.duration_ms,
                }),
            )
            if ev.event_hash != expect:
                return False, ev.seq
            prev = ev.event_hash
        return True, None

    def load(self, events: Iterable[dict[str, Any]]) -> "TraceLedger":
        """从 plain 事件列表重建（round-trip）；不校验，供 load 后 verify()。"""
        self._events = []
        self._last_hash = None
        for d in events:
            ev = TraceEvent.from_plain(d)
            self._events.append(ev)
            self._last_hash = ev.event_hash
        return self


__all__ = ["TraceEvent", "TraceLedger"]
