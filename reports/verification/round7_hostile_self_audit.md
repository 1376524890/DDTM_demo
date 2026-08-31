# Round 7 Hostile Self-Audit

Evaluated commit: `d2537beab7fb6c4694e718f73bff132767cbe75f`

## Findings

- `valor/privacy_audit/voi.py`: `tamper_openings` scenario flag remains (TEST_FIXTURE only); should move to `TamperingSellerProvider`.
- `replay_consistent` legacy parameter retained for compatibility; G50 no longer trusts it.
- `final_eval_accessed_before_decision` legacy parameter retained; G37 now requires `TerminalDecisionArtifact`.
