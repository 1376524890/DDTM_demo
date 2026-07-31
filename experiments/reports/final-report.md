# DDTM-QAS Final Report (G0 + G1)

- **G0:** PASS
- **G1:** PASS
- **Git Working Tree:** DIRTY
- **Canonical Specification:** DDTM-CANONICAL-V1
- **Poseidon Parameters:** DDTM-POSEIDON2-BN254-V1

## G0 — statistical & economic baseline
- SPRT lower (accept) = -2.985682
- SPRT upper (reject) = 4.553877
- Bad-quality detection probability = 0.951215
- Minimum bond = 3141.0880
- Objective cost = 1020.4577
- Probability conservation error = 1.53e-14 (< 1e-12)
- Three-run determinism = 0.00e+00 (< 1e-12)
- Cost reconstruction error = 0.00e+00 (< 1e-9)
- Inconclusive action = block_settlement

## G1 — cross-language deterministic data layer
- Schema SHA-256: `81814bd387b45aaf5394f454efeb98709911a1a53b8d897cee1ab713f62936f5`
- Positive cases: 17/17 (all PASS in Go/Rust; gnark in-circuit verified)
- Negative cases (NaN/+Inf/-Inf rejected): 3/3
- Generated scale cases: 2/2 (capacity 8192; production 131072 identical path)
- Cross-language root mismatches: 0

| Implementation | passed | failed | skipped |
|---|---:|---:|---:|
| Python (manifest golden) | 22 | 0 | 0 |
| Go | 22 | 0 | 0 |
| Rust | 22 | 0 | 0 |
| gnark (in-circuit) | 19 | 0 | 3 |

## Gate files
- `experiments/raw/g0-result.json`
- `experiments/raw/g1-go.json`, `g1-rust.json`, `g1-gnark.json`
- `experiments/raw/g1-gate.json`
- `experiments/vectors/manifest.json`

## Reproducibility
- Git commit: `c72d8fe7b6e93c1e27e98864a845469b7bb057b4`
- Config SHA-256: `742ecbbf94260379cd5973705a05db5d9a71e2434f5f3fb565ebaa43fed70293`
- Optimizer SHA-256: `a4dd52e5b760b6b769288f72a924c22a87a59ffb2e499b1b4e39a1e935cc7e0b`
- Host: codeserver (Linux-6.8.0-134-generic-x86_64-with-glibc2.39)

_The same `dataRoot` is now safely referenceable by the TEE evaluator, the_
_ZKP circuits, and the buyer delivery review._
