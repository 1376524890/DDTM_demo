# Round 7 Hostile Self-Audit

Evaluated commit: `bfa0926d9ee09c74b4d45eb0e34dcdc9c8bad763`

## Findings

- `valor/privacy_audit/voi.py`: `tamper_openings` scenario flag remains (TEST_FIXTURE only); should move to `TamperingSellerProvider`.
- `replay_consistent` legacy parameter retained for compatibility; G50 no longer trusts it.
- `final_eval_accessed_before_decision` legacy parameter retained; G37 now requires `TerminalDecisionArtifact`.
