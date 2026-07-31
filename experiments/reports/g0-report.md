# G0 Report — Statistical & Economic Baseline

- **Git commit:** `c72d8fe7b6e93c1e27e98864a845469b7bb057b4`
- **Working tree:** DIRTY
- **Config SHA-256:** `742ecbbf94260379cd5973705a05db5d9a71e2434f5f3fb565ebaa43fed70293`
- **Optimizer SHA-256:** `a4dd52e5b760b6b769288f72a924c22a87a59ffb2e499b1b4e39a1e935cc7e0b`
- **Dataset SHA-256:** `6195a11d2e2cafa3bc901b9f984ab6d67d6e3928d93ae40f6092ccf2ac6babd0`

## SPRT boundaries
- lower (accept) = -2.985682
- upper (reject) = 4.553877

## JABO economics
- Bad-quality detection probability = 0.951215
- Minimum bond = 3141.087960
- Objective cost = 1020.457699

> Audit cost evaluated at epsilon = tau_good
> Residual loss evaluated at epsilon = tau_bad
> Inconclusive action = block_settlement

| Component | Value |
|---|---:|
| row_audit_cost | 14.133320 |
| proof_batch_cost | 26.124897 |
| audit_cost | 40.258217 |
| bond_capital_cost | 4.819203 |
| residual_loss | 975.380279 |
| **objective_cost** | **1020.457699** |

## Operating points
| contamination | P(accept) | P(reject) | P(inconc) | E[T] | E[ceil(T/64)] |
|---:|---:|---:|---:|---:|---:|
| 0.0 | 1.000000e+00 | 0.000000e+00 | 0.000000e+00 | 56.0000 | 1.0000 |
| 0.01 | 1.000000e+00 | 5.164752e-10 | 2.511539e-56 | 64.9408 | 1.4317 |
| 0.02 | 9.999996e-01 | 3.638386e-07 | 5.454383e-30 | 77.1982 | 1.7128 |
| 0.03 | 9.999759e-01 | 2.408733e-05 | 3.436541e-17 | 95.2908 | 2.0049 |
| 0.05 | 9.921153e-01 | 7.876029e-03 | 8.662768e-06 | 176.6665 | 3.2656 |
| 0.08 | 3.436533e-01 | 6.497705e-01 | 6.576184e-03 | 365.9637 | 6.2075 |
| 0.1 | 4.876901e-02 | 9.512150e-01 | 1.598481e-05 | 214.3377 | 3.8370 |
| 0.12 | 7.213834e-03 | 9.927862e-01 | 2.300861e-10 | 133.7295 | 2.5749 |
| 0.15 | 5.087683e-04 | 9.994912e-01 | 1.209214e-20 | 83.1483 | 1.7718 |
| 0.2 | 8.218597e-06 | 9.999918e-01 | 1.285087e-43 | 50.7285 | 1.2327 |

## Gate
| Check | Criterion | Result | Status |
|---|---|---:|---|
| Probability conservation | max|P+R+I-1| < 1e-12 | 1.53e-14 | PASS |
| Three-run determinism | max_diff < 1e-12 | 0.00e+00 | PASS |
| Cost reconstruction | |J-sum(parts)| < 1e-9 | 0.00e+00 | PASS |
| Working tree (release) | CLEAN | DIRTY | FAIL |
