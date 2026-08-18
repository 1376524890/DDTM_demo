# VALOR-v1 Final Mechanism Closure v2

- HEAD: `d06e5f1`
- Worktree: clean
- Full pytest: 285 passed
- Mechanism invariant scan: PASS
- Mutation tests: 7 passed
- Mutation survivors: 0

## Decision

```
unresolved_P0 = 6
unresolved_mechanism_gaps = 3
mutation_survivors = 0
paper_mechanism_closure = FAIL
```

## Unresolved P0

- P0-D: R_cal is not yet fully distributed commit-challenge in `calibration_runner`.
- P0-E: independent R_cert full-policy envelope is not fully rerun.
- P0-C: action profile binding to likelihood/certificate is still partial.
- P0-Q: pricing provenance is improved but not fully DAG-audited.
- P0-S: bond capital timeline still uses scenario `t_pre/t_post`.
- P0-T: FullChainGate mutation coverage is still partial.

## Remaining Mechanism Gaps

- Scenario matrix C10/C11/C12 not implemented.
- Coverage JSON is still hand-authored rather than machine-generated.
- Reverse self-audit provenance graph is not fully machine-verified.

Machine-readable source: `reports/final_mechanism_closure_v2.json`.
