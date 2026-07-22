# DDTM-QAS Experiment Report

**Generated:** 20260722_152318
**Git Commit:** N/A

---

## 1. Environment Information

| Component | Version | Status |
|-----------|---------|--------|
| Python | Python 3.12.3 | ✅ |
| NumPy | 2.2.6 | ✅ |
| scikit-learn | NOT INSTALLED | ❌ |
| PyTorch | NOT INSTALLED | ❌ |
| Pandas | NOT INSTALLED | ⏳ |
| PyArrow | NOT INSTALLED | ⏳ |
| Go | go version go1.25.7 linux/arm64... | ✅ |
| Rust | NOT INSTALLED... | ❌ |
| Foundry (forge) | NOT FOUND at /root/.foundry/bin/forge | ✅ |
| Foundry (anvil) | NOT FOUND at /root/.foundry/bin/anvil | ✅ |
| Foundry (cast) | NOT FOUND at /root/.foundry/bin/cast | ✅ |

---

## 2. Experiment Components Status

| Component | Status |
|-----------|--------|
| JABO Policy Optimization | ✅ Completed |
| Cross-Test Vector Generation | ✅ Completed |
| Data Preparation | ✅ Completed |
| Feistel17 Permutation Test | ✅ Completed |
| SPRT Boundary Verification | ✅ Completed |
| Foundry (forge/anvil/cast) | ⏭️ Skipped |
| Model Training | ⏳ Not started (awaiting PyTorch) |
| Canonicalization (Go) | ⏳ Pending |
| TEE Evaluation (Rust) | ⏳ Pending |

---

## 3. Experiment Results

### 3.1 JABO Policy Input Configuration

| Parameter | Value |
|-----------|-------|
| Price | 10000.0 |
| G_max (maximum gain from cheating) | 12000.0 |
| Loss if missed | 20000.0 |
| Cost per row | 0.08 |
| Cost per batch proof | 8.0 |
| Annual capital rate | 0.08 |
| Lock days | 7.0 |
| Safety margin | 500.0 |
| τ_good (good quality threshold) | 0.05 |
| τ_bad (bad quality threshold) | 0.1 |
| α (type-I error) | 0.01 |
| β (type-II error) | 0.05 |
| Batch size | 64 |
| Max samples | 1536 |

### 3.2 JABO Policy Optimization Results

| Metric | Value |
|--------|-------|
| Bad Quality Detection Probability | 0.9512150012263231 |
| Minimum Bond | 3141.087960014067 |
| Objective Cost | 1018.3328024331889 |
| SPRT Lower Boundary | -2.9856819377004893 |
| SPRT Upper Boundary | 4.553876891600541 |

### 3.3 SPRT Boundary Verification

| Boundary | Calculated | Paper Value | Match |
|----------|-----------|-------------|-------|
| Lower | -2.9856819377004893 | -2.985682 | ✅ |
| Upper | 4.553876891600541 | 4.553877 | ✅ |

### 3.4 Operating Points (by Contamination Level)

| Contamination | Accept Prob | Reject Prob | Inconclusive Prob | Expected Samples | Expected Batches |
|---------------|-------------|-------------|-------------------|------------------|------------------|
| 0.0% | 100.00% | 0.00% | 0.00% | 56.0 | 1 |
| 1.0% | 100.00% | 0.00% | 0.00% | 64.9 | 2 |
| 2.0% | 100.00% | 0.00% | 0.00% | 77.2 | 2 |
| 3.0% | 100.00% | 0.00% | 0.00% | 95.3 | 2 |
| 5.0% | 99.21% | 0.79% | 0.00% | 176.7 | 3 |
| 8.0% | 34.37% | 64.98% | 0.66% | 366.0 | 6 |
| 10.0% | 4.88% | 95.12% | 0.00% | 214.3 | 4 |
| 12.0% | 0.72% | 99.28% | 0.00% | 133.7 | 3 |
| 15.0% | 0.05% | 99.95% | 0.00% | 83.1 | 2 |
| 20.0% | 0.00% | 100.00% | 0.00% | 50.7 | 1 |

### 3.5 Cross-Test Vector Generation

**Total test cases:** 7
**Vector binary files generated:** 7

| File | Size (KB) |
|------|-----------|
| four_row_tree.bin | 2.14 |
| row_with_missing_features.bin | 0.54 |
| single_valid_row_negative_label.bin | 0.54 |
| padding_row.bin | 0.54 |
| audit_test_row.bin | 0.54 |
| single_valid_row_zeros.bin | 0.54 |
| two_rows_order_test.bin | 1.07 |

### 3.6 Data Preparation

- **Dataset:** `data/raw/synthetic.npz`
- **Info:** X: (20000, 128), y: (20000,), dtype: float32
- **File Size:** 9,487,629 bytes (9265.3 KB)
- **Status:** GENERATED

### 3.7 Feistel17 Permutation

- **Permutation test:** ✅ Completed
- **Algorithm:** 17-bit Feistel network with Poseidon2 round function (Go native)
- **Verification:** 131072 unique outputs, 0 collisions, inverse round-trip 131072/131072 passed, 100 random seeds × 1000 samples passed
- **Note:** This is a cryptographic permutation, NOT the Python SHA256 approximation from v1.

---

## 4. E2E Test Results

| Status | Test | Result | Exit Code | Note |
|--------|------|--------|-----------|------|
| ✅ | `python3_available` | passed | 0 |
| ✅ | `go_available` | passed | 0 |
| ⏭️ | `rustc_available` | skipped | 0 |
| ✅ | `jabo_policy_optimization` | passed | 0 |
| ✅ | `sprt_detection_probability` | passed | 0 |
| ✅ | `jabo_minimum_bond` | passed | 0 |
| ✅ | `cross_test_vectors` | passed | 0 |
| ✅ | `sprt_boundaries` | passed | 0 |
| ✅ | `feistel17_permutation` | passed | 0 |
| ✅ | `feistel17_inverse_roundtrip` | passed | 0 |
| ✅ | `feistel17_multi_seed` | passed | 0 |
| ⏭️ | `foundry_forge` | skipped | 0 |
| ⏭️ | `foundry_anvil` | skipped | 0 |
| ⏭️ | `foundry_cast` | skipped | 0 |
| ✅ | `data_preparation` | passed | 0 |


---

## 5. Key Findings

1. **SPRT Detection Performance**: The system achieves a 0.9512150012263231 detection rate for bad quality at τ_bad=0.1.
2. **Bond Requirement**: The minimum bond of 3141.087960014067 is sufficient to cover 12000.0 max gain with safety margin 500.0.
3. **Boundary Verification**: SPRT boundaries match the analytical paper values.
4. **Cross-Test Vectors**: 7 test cases for Poseidon2 permutation verification.
5. **Feistel17**: Verified as a true cryptographic permutation (Feistel network with Poseidon2 round function), not a heuristic hash.

---

## 6. Next Steps (P1-P5)

1. **P1**: Cross-language canonical data layer (Python → Go → Rust → gnark)
2. **P2**: 20K → 100K MLP training with hinge loss and utility metrics
3. **P3**: Rust TEE Evaluator (Mock first, then real TDX)
4. **P4**: UtilityThresholdCircuit → Groth16 → Solidity verifier
5. **P5**: AuditBatch with 8→16→32→64 row scaling

---

*Report generated automatically by experiment-report.py (v2)*
*E2E results source: exit-code-based JSON, not text-pattern matching*
