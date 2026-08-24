"""BondTimeline (Round 5 §20).

Replaces t_pre/t_post/t_b scalar scenario durations with an event-based capital
timeline: PRELOCK -> ADJUST -> USAGE_BOND_LOCK -> RELEASE/SLASH.

C_B_cap = κ ∫ B(t) dt is computed by trapezoidal integration over the frozen
logical event sequence (same source as MoneyLedger).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BondTimelineEvent:
    kind: str  # PRELOCK | ADJUST | USAGE_BOND_LOCK | RELEASE | SLASH
    event_seq: int
    account: str
    amount: float
    time: float = 0.0

    def to_plain(self) -> dict:
        return {
            "kind": self.kind, "event_seq": self.event_seq,
            "account": self.account, "amount": self.amount, "time": self.time,
        }


@dataclass
class BondTimeline:
    events: list[BondTimelineEvent] = field(default_factory=list)

    def add_event(self, kind: str, account: str, amount: float, time: float = 0.0) -> BondTimelineEvent:
        ev = BondTimelineEvent(
            kind=kind, event_seq=len(self.events) + 1,
            account=account, amount=float(amount), time=float(time),
        )
        self.events.append(ev)
        return ev

    def capital_cost(self, *, kappa: float, account: str) -> float:
        """C_B_cap = κ ∫ B(t) dt over this account's event timeline."""
        if not self.events or kappa <= 0:
            return 0.0
        relevant = sorted(
            [e for e in self.events if e.account == account],
            key=lambda e: (e.time, e.event_seq),
        )
        if not relevant:
            return 0.0
        total = 0.0
        for i, ev in enumerate(relevant):
            if i + 1 < len(relevant):
                nxt = relevant[i + 1]
                total += ev.amount * (nxt.time - ev.time)
        return kappa * total

    def to_plain(self) -> dict:
        return {
            "events": [e.to_plain() for e in self.events],
            "capital_cost_seller": self.capital_cost(kappa=1.0, account="B_S"),
            "capital_cost_buyer": self.capital_cost(kappa=1.0, account="B_B_use"),
        }


__all__ = ["BondTimeline", "BondTimelineEvent"]
