# Round 7 Hostile Self-Audit

Evaluated commit: `beb4f06777bd9ba58c99ccf8181fb235c6136bd5`

## Findings

- `valor/privacy_audit/voi.py`: `tamper_openings` scenario flag remains (TEST_FIXTURE only); should move to `TamperingSellerProvider`.
- `replay_consistent` legacy parameter retained for compatibility; G50 no longer trusts it.
- `final_eval_accessed_before_decision` legacy parameter retained; G37 now requires `TerminalDecisionArtifact`.
