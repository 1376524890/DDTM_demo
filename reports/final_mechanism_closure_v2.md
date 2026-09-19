# VALOR-v1 Final Mechanism Closure v2

> ⚠️ **SUPERSEDED / 过期报告**：本报告（HEAD `d06e5f1`，285 passed）为 v2，已被 Round 7 机器验证取代。
> 当前权威状态见 `reports/verification/final_mechanism_closure_v3.json`（评估 commit `d2537be`）：
> **paper_closure_gate = FAIL**（56 项中 38 通过、18 失败），未闭合 P0 4 项。
> 本报告历史结论 `paper_mechanism_closure = FAIL` 方向正确，但具体 P0/缺口清单与数字已过时。

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
