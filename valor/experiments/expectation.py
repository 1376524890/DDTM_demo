"""ExperimentExpectation — test-harness-only expectations (Round 5 §23).

Production mechanism requests (usage_requests / training_requests) must NOT
carry expected outcomes; only the test harness reads this structure.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentExpectation:
    """Expected outcome for a specific experiment request."""

    request_key: str
    expected: str  # ALLOW | DENY | ...

    def to_plain(self) -> dict:
        return {"request_key": self.request_key, "expected": self.expected}


__all__ = ["ExperimentExpectation"]
