"""FinalEvaluationAccessLedger (Round 5 §24)."""

from __future__ import annotations

from dataclasses import dataclass, field

from valor.core.hashing import content_hash


@dataclass(frozen=True)
class FinalEvaluationAccessRecord:
    caller: str
    stage: str
    event_seq: int
    role: str
    reason: str

    def to_plain(self) -> dict:
        return {
            "caller": self.caller, "stage": self.stage,
            "event_seq": self.event_seq, "role": self.role, "reason": self.reason,
        }


@dataclass
class FinalEvaluationAccessLedger:
    records: list[FinalEvaluationAccessRecord] = field(default_factory=list)
    _seq: int = 0

    def record(self, *, caller: str, stage: str, role: str, reason: str) -> FinalEvaluationAccessRecord:
        self._seq += 1
        rec = FinalEvaluationAccessRecord(
            caller=caller, stage=stage, event_seq=self._seq, role=role, reason=reason)
        self.records.append(rec)
        return rec

    def to_plain(self) -> dict:
        return {
            "records": [r.to_plain() for r in self.records],
            "hash": content_hash([r.to_plain() for r in self.records]),
        }


__all__ = ["FinalEvaluationAccessLedger", "FinalEvaluationAccessRecord"]
