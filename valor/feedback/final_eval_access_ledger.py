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


class FinalEvaluationHandle:
    """Round 6 Phase 18: raw FinalEval arrays live only inside this handle.

    Evaluators must call resolve() to obtain the data. resolve() records an
    access attempt and raises FINAL_EVALUATION_ACCESS_FORBIDDEN before the
    terminal state is frozen.
    """

    def __init__(self, *, X, y, indices, ledger: FinalEvaluationAccessLedger) -> None:
        self._X = X
        self._y = y
        self._indices = tuple(sorted(int(i) for i in indices))
        self._ledger = ledger

    def resolve(self, *, stage: str, caller: str, terminal_state) -> tuple:
        """Return (final_X, final_y) only after terminal state is frozen."""
        import numpy as np

        if str(terminal_state) != "TRADE":
            self._ledger.record(
                caller=caller, stage=stage, role="R_eval",
                reason="FINAL_EVALUATION_ACCESS_FORBIDDEN")
            raise ValueError("FINAL_EVALUATION_ACCESS_FORBIDDEN")
        self._ledger.record(
            caller=caller, stage=stage, role="R_eval",
            reason="terminal_frozen_feedback_resolution")
        idx = np.sort(np.asarray(self._indices, dtype=int))
        final_X = self._X.iloc[idx].reset_index(drop=True)
        final_y = self._y.iloc[idx].reset_index(drop=True)
        return final_X, final_y

    def ledger(self) -> FinalEvaluationAccessLedger:
        return self._ledger
