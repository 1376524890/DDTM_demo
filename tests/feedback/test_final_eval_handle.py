"""Round 6 Phase 18: FinalEvaluationAccessGuard blocks pre-terminal access."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from valor.feedback.final_eval_access_ledger import (
    FinalEvaluationAccessLedger, FinalEvaluationHandle, TerminalDecisionArtifact,
)


def _data():
    X = pd.DataFrame({"a": np.arange(10.0)})
    y = pd.Series(np.arange(10))
    return X, y


def test_pre_terminal_access_forbidden():
    X, y = _data()
    ledger = FinalEvaluationAccessLedger()
    handle = FinalEvaluationHandle(X=X, y=y, indices=[2, 4], ledger=ledger)
    with pytest.raises(ValueError, match="FINAL_EVALUATION_ACCESS_FORBIDDEN"):
        handle.resolve(stage="DATA_VOI", caller="orch", terminal_state="NO_TRADE")
    assert any(r.reason == "FINAL_EVALUATION_ACCESS_FORBIDDEN"
               for r in ledger.records)


def test_post_terminal_access_allowed():
    X, y = _data()
    ledger = FinalEvaluationAccessLedger()
    handle = FinalEvaluationHandle(X=X, y=y, indices=[2, 4], ledger=ledger)
    art = TerminalDecisionArtifact(terminal="TRADE", stage="FEEDBACK")
    fx, fy = handle.resolve(stage="FEEDBACK", caller="orch", terminal_artifact=art)
    assert list(fx["a"]) == [2.0, 4.0]
    assert list(fy) == [2, 4]
    assert all(r.stage == "FEEDBACK" for r in ledger.records)
    assert art.artifact_hash


def test_missing_terminal_artifact_forbidden():
    X, y = _data()
    ledger = FinalEvaluationAccessLedger()
    handle = FinalEvaluationHandle(X=X, y=y, indices=[2, 4], ledger=ledger)
    with pytest.raises(ValueError, match="FINAL_EVALUATION_ACCESS_FORBIDDEN"):
        handle.resolve(stage="FEEDBACK", caller="orch")
    assert any(r.reason == "FINAL_EVALUATION_ACCESS_FORBIDDEN"
               for r in ledger.records)


def test_pre_terminal_artifact_stage_forbidden():
    X, y = _data()
    ledger = FinalEvaluationAccessLedger()
    handle = FinalEvaluationHandle(X=X, y=y, indices=[2, 4], ledger=ledger)
    art = TerminalDecisionArtifact(terminal="TRADE", stage="DATA_VOI")
    with pytest.raises(ValueError, match="FINAL_EVALUATION_ACCESS_FORBIDDEN"):
        handle.resolve(stage="FEEDBACK", caller="orch", terminal_artifact=art)

