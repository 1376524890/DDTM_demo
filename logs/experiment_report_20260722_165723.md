# DDTM-QAS Experiment Report

**Generated:** 20260722_165723
**Git Commit:** 131c37e git: 移除大型向量文件(>50MB)跟踪，改为按需生成
**Working Tree:** DIRTY

---

## 0. Experiment Metadata

| Field | Value |
|-------|-------|
| Git Commit SHA | `131c37eb99f8e76bfeab82b42bf630c26d2dbb82` |
| Working Tree Status | DIRTY |
| Config SHA-256 | `969b7acc87dcc07fe0eea076b7c55f01a71c9626c60eca89f113fbab16194f68` |
| Optimizer SHA-256 | `c8233d1088ed269ebac3cd8f31c1b4bbeb44492386db5a42c0e56ef16fcb5b1a` |
| Host | 42cc357abe29 |
| CPU | Cortex-A55 |
| Memory | 15.4 GB |
| OS | Linux 5.4.96-17-kr9a0 aarch64 |

---

## 1. Environment Information

| Component | Version | Status |
|-----------|---------|--------|
| Python | Python 3.12.3 | ✅ |
| NumPy | 2.2.6 | ✅ |
| scikit-learn | NOT INSTALLED | ⏳ |
| PyTorch | NOT INSTALLED | ⏳ |
| Pandas | NOT INSTALLED | ⏳ |
| PyArrow | NOT INSTALLED | ⏳ |
| Go | go version go1.25.7 linux/arm64... | ✅ |
| Rust | NOT INSTALLED... | ⏭️ |
| Foundry (forge) | NOT FOUND at /root/.foundry/bin/forge | ⏭️ |
| Foundry (anvil) | NOT FOUND at /root/.foundry/bin/anvil | ⏭️ |
| Foundry (cast) | NOT FOUND at /root/.foundry/bin/cast | ⏭️ |

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
| Objective Cost | 1020.4576994582761 |
| SPRT Lower Boundary | -2.9856819377004893 |
| SPRT Upper Boundary | 4.553876891600541 |

### 3.3 Objective Cost Breakdown

| Component | Formula | Value |
|-----------|---------|-------|
| Row Audit Cost | c_r · E[T] | 14.133319719165389 |
| Proof Batch Cost | c_p · E[K] | 26.12489702508718 |
| Audit Cost (subtotal) | row + proof | 40.258216744252564 |
| Bond Capital Cost | r_B · B · T_lock / 365 | 4.819203445501034 |
| Residual Loss | L_max · p_miss | 975.3802792685225 |
| **Total Objective Cost** | **J = audit + capital + loss** | **1020.4576994582761** |

### 3.4 SPRT Boundary Verification

| Boundary | Calculated | Paper Value | Match |
|----------|-----------|-------------|-------|
| Lower | -2.9856819377004893 | -2.985682 | ✅ |
| Upper | 4.553876891600541 | 4.553877 | ✅ |

### 3.5 Operating Points (by Contamination Level)

| Contamination | Accept Prob | Reject Prob | Inconclusive Prob | Expected Samples | Expected Batches |
|---------------|-------------|-------------|-------------------|------------------|------------------|
| 0.0% | 100.00% | 0.00% | 0.00% | 56.0 | 1.0 |
| 1.0% | 100.00% | 0.00% | 0.00% | 64.9 | 1.4317488620474326 |
| 2.0% | 100.00% | 0.00% | 0.00% | 77.2 | 1.7128004421647371 |
| 3.0% | 100.00% | 0.00% | 0.00% | 95.3 | 2.004851954615341 |
| 5.0% | 99.21% | 0.79% | 0.00% | 176.7 | 3.2656121281358974 |
| 8.0% | 34.37% | 64.98% | 0.66% | 366.0 | 6.207502043088361 |
| 10.0% | 4.88% | 95.12% | 0.00% | 214.3 | 3.8370412365590996 |
| 12.0% | 0.72% | 99.28% | 0.00% | 133.7 | 2.5748880239925143 |
| 15.0% | 0.05% | 99.95% | 0.00% | 83.1 | 1.7717871597334374 |
| 20.0% | 0.00% | 100.00% | 0.00% | 50.7 | 1.2327417795046578 |

### 3.6 Cross-Test Vector Generation

**Total test cases:** 7
**Vector binary files generated:** 27

| File | Size (KB) |
|------|-----------|
| tc01_all_zeros.bin | 0.54 |
| tc14_same_data_diff_rowid.bin | 1.07 |
| four_row_tree.bin | 2.14 |
| tc06_row_order.bin | 1.07 |
| tc08_int32_max.bin | 0.54 |
| tc12_nan_sentinel.bin | 0.54 |
| tc13_infinity_clamp.bin | 0.54 |
| tc18_large_100k.bin | 53515.62 |
| tc09_int32_min.bin | 0.54 |
| row_with_missing_features.bin | 0.54 |
| tc19_capacity_padding.bin | 70144.0 |
| tc07_audit_test.bin | 0.54 |
| tc17_label_mutation.bin | 1.07 |
| tc04_padding_row.bin | 0.54 |
| tc16_single_bit_mutation.bin | 1.07 |
| single_valid_row_negative_label.bin | 0.54 |
| tc02_negative_label.bin | 0.54 |
| padding_row.bin | 0.54 |
| tc03_missing_features.bin | 0.54 |
| tc10_q16_pos_boundary.bin | 0.54 |
| tc11_q16_neg_boundary.bin | 0.54 |
| audit_test_row.bin | 0.54 |
| tc20_missing_vs_zero.bin | 1.07 |
| single_valid_row_zeros.bin | 0.54 |
| tc05_four_row_tree.bin | 2.14 |
| tc15_identical_rows.bin | 1.07 |
| two_rows_order_test.bin | 1.07 |

### 3.6 Data Preparation

- **Dataset:** `data/raw/synthetic.npz`
- **Info:** X: (20000, 128), y: (20000,), dtype: float32
- **File Size:** 9,487,629 bytes (9265.3 KB)
- **Status:** GENERATED

### 3.8 Feistel17 Permutation

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

## Appendix A: Raw JABO Policy Result

```json
{
  "policy": {
    "tau_good": 0.05,
    "tau_bad": 0.1,
    "alpha": 0.01,
    "beta": 0.05,
    "batch_size": 64,
    "max_samples": 1536
  },
  "sprt_boundaries": {
    "lower": -2.9856819377004893,
    "upper": 4.553876891600541
  },
  "minimum_bond": 3141.087960014067,
  "bad_quality_detection_probability": 0.9512150012263231,
  "cost_breakdown": {
    "row_audit_cost": 14.133319719165389,
    "proof_batch_cost": 26.12489702508718,
    "audit_cost": 40.258216744252564,
    "bond_capital_cost": 4.819203445501034,
    "residual_loss": 975.3802792685225,
    "objective_cost": 1020.4576994582761
  },
  "operating_points": [
    {
      "contamination": 0.0,
      "accept_probability": 1.0,
      "reject_probability": 0.0,
      "inconclusive_probability": 0.0,
      "expected_samples": 56.0,
      "expected_batches": 1.0
    },
    {
      "contamination": 0.01,
      "accept_probability": 0.9999999994835244,
      "reject_probability": 5.164751893013958e-10,
      "inconclusive_probability": 2.511538923620669e-56,
      "expected_samples": 64.9408221710254,
      "expected_batches": 1.4317488620474326
    },
    {
      "contamination": 0.02,
      "accept_probability": 0.9999996361613911,
      "reject_probability": 3.638386073809602e-07,
      "inconclusive_probability": 5.454382853771685e-30,
      "expected_samples": 77.19822904388357,
      "expected_batches": 1.7128004421647371
    },
    {
      "contamination": 0.03,
      "accept_probability": 0.9999759126706365,
      "reject_probability": 2.408732936082607e-05,
      "inconclusive_probability": 3.436540810771681e-17,
      "expected_samples": 95.29075211786564,
      "expected_batches": 2.004851954615341
    },
    {
      "contamination": 0.05,
      "accept_probability": 0.992115308646786,
      "reject_probability": 0.00787602858513095,
      "inconclusive_probability": 8.662768075271022e-06,
      "expected_samples": 176.66649648956735,
      "expected_batches": 3.2656121281358974
    },
    {
      "contamination": 0.08,
      "accept_probability": 0.34365329038433734,
      "reject_probability": 0.6497705253074212,
      "inconclusive_probability": 0.0065761843082567575,
      "expected_samples": 365.9636827835534,
      "expected_batches": 6.207502043088361
    },
    {
      "contamination": 0.1,
      "accept_probability": 0.048769013963426124,
      "reject_probability": 0.9512150012263231,
      "inconclusive_probability": 1.5984810256057562e-05,
      "expected_samples": 214.33772095090913,
      "expected_batches": 3.8370412365590996
    },
    {
      "contamination": 0.12,
      "accept_probability": 0.007213834144008569,
      "reject_probability": 0.9927861656259056,
      "inconclusive_probability": 2.3008608333515833e-10,
      "expected_samples": 133.72946170354166,
      "expected_batches": 2.5748880239925143
    },
    {
      "contamination": 0.15,
      "accept_probability": 0.0005087682923159767,
      "reject_probability": 0.9994912317076795,
      "inconclusive_probability": 1.209214238465417e-20,
      "expected_samples": 83.14825590071453,
      "expected_batches": 1.7717871597334374
    },
    {
      "contamination": 0.2,
      "accept_probability": 8.21859740815264e-06,
      "reject_probability": 0.9999917814025943,
      "inconclusive_probability": 1.2850874962619751e-43,
      "expected_samples": 50.72845363785564,
      "expected_batches": 1.2327417795046578
    }
  ]
}
```

## Appendix B: E2E Test Results (Raw JSON)

```json
[
  {
    "test_name": "python3_available",
    "status": "passed",
    "expected_unique": 0,
    "actual_unique": 0,
    "exit_code": 0
  },
  {
    "test_name": "go_available",
    "status": "passed",
    "expected_unique": 0,
    "actual_unique": 0,
    "exit_code": 0
  },
  {
    "test_name": "rustc_available",
    "status": "skipped",
    "expected_unique": 0,
    "actual_unique": 0,
    "exit_code": 0
  },
  {
    "test_name": "jabo_policy_optimization",
    "status": "passed",
    "expected_unique": 0,
    "actual_unique": 0,
    "exit_code": 0
  },
  {
    "test_name": "sprt_detection_probability",
    "status": "passed",
    "expected_unique": 0,
    "actual_unique": 0,
    "exit_code": 0
  },
  {
    "test_name": "jabo_minimum_bond",
    "status": "passed",
    "expected_unique": 0,
    "actual_unique": 0,
    "exit_code": 0
  },
  {
    "test_name": "cross_test_vectors",
    "status": "passed",
    "expected_unique": 0,
    "actual_unique": 0,
    "exit_code": 0
  },
  {
    "test_name": "sprt_boundaries",
    "status": "passed",
    "expected_unique": 0,
    "actual_unique": 0,
    "exit_code": 0
  },
  {
    "test_name": "feistel17_permutation",
    "status": "passed",
    "expected_unique": 131072,
    "actual_unique": 131072,
    "exit_code": 0
  },
  {
    "test_name": "feistel17_inverse_roundtrip",
    "status": "passed",
    "expected_unique": 131072,
    "actual_unique": 131072,
    "exit_code": 0
  },
  {
    "test_name": "feistel17_multi_seed",
    "status": "passed",
    "expected_unique": 0,
    "actual_unique": 0,
    "exit_code": 0
  },
  {
    "test_name": "foundry_forge",
    "status": "skipped",
    "expected_unique": 0,
    "actual_unique": 0,
    "exit_code": 0
  },
  {
    "test_name": "foundry_anvil",
    "status": "skipped",
    "expected_unique": 0,
    "actual_unique": 0,
    "exit_code": 0
  },
  {
    "test_name": "foundry_cast",
    "status": "skipped",
    "expected_unique": 0,
    "actual_unique": 0,
    "exit_code": 0
  },
  {
    "test_name": "data_preparation",
    "status": "passed",
    "expected_unique": 0,
    "actual_unique": 0,
    "exit_code": 0
  }
]
```

## Appendix C: G0 Convergence Verification

| Check | Criterion | Result | Status |
|-------|-----------|--------|--------|
| Probability Conservation | max\|PA+PR+PI-1\| < 1e-12 | 1.53e-14 | PASS |
| Three-Run Determinism | max_diff < 1e-12 | 0.00 | PASS |
| Cost Reconstruction | \|J - sum(parts)\| < 1e-9 | 0.00 | PASS |
| Working Tree Status | CLEAN | DIRTY | FAIL |

---

## Appendix D: G1 Vectors Summary

| # | Vector | Rows | Blob Size (bytes) | SHA-256 (first 32 hex) |
|---|--------|------|--------------------|------------------------|
| tc01_all_zeros | 1 | 548 | e5d2a4bc0e243690b203e4d85d72c9e6... |
| tc02_negative_label | 1 | 548 | 71bd23e9316c44bb235074cabd115dd7... |
| tc03_missing_features | 1 | 548 | 0d3c7a2ec3d1f86eaafd0ee46195fc1f... |
| tc04_padding_row | 1 | 548 | 8a14944094fd5ebfa9c1e5f0dfcdc33c... |
| tc05_four_row_tree | 4 | 2,192 | 37ee5d6e21c07bef13a5c3502115059d... |
| tc06_row_order | 2 | 1,096 | 187383178045539cecdf44564fe52b10... |
| tc07_audit_test | 1 | 548 | 187289ce3969ca2131be7811df4cea78... |
| tc08_int32_max | 1 | 548 | 79e5321a389638ae44daf9093409b0ad... |
| tc09_int32_min | 1 | 548 | b80c74689f8646d7a5afae32e057d78e... |
| tc10_q16_pos_boundary | 1 | 548 | e5cbae9150a2e33d90f563de9a2f5b79... |
| tc11_q16_neg_boundary | 1 | 548 | 0fd1c785817f1b4172eec596704cc5ea... |
| tc12_nan_sentinel | 1 | 548 | 79e5321a389638ae44daf9093409b0ad... |
| tc13_infinity_clamp | 1 | 548 | e842d237be8cd4b373bf6f5ac1dd9fc7... |
| tc14_same_data_diff_rowid | 2 | 1,096 | d996f5df3c94beff0c8ceb5f3e879c76... |
| tc15_identical_rows | 2 | 1,096 | 22a5fd60eb9167a12825cdd134521e8f... |
| tc16_single_bit_mutation | 2 | 1,096 | 19a034b4fba74bbe96e406b9dbcfb6b1... |
| tc17_label_mutation | 2 | 1,096 | b10ca435fb19c41ae89e740fe7ee7559... |
| tc18_large_100k | 100000 | 54,800,000 | 418771baf60b06b7496e3f7c8da4ff6a... |
| tc19_capacity_padding | 131072 | 71,827,456 | 844933eedadc2cd459b5d2fc0894cdcc... |
| tc20_missing_vs_zero | 2 | 1,096 | 680912d83546e1a9993f4b50eff0164d... |


---

## Appendix E: Experiment Configuration

```json
{
  "price": 10000.0,
  "g_max": 12000.0,
  "loss_if_missed": 20000.0,
  "cost_per_row": 0.08,
  "cost_per_batch_proof": 8.0,
  "annual_capital_rate": 0.08,
  "lock_days": 7.0,
  "safety_margin": 500.0,
  "tau_good": 0.05,
  "tau_bad": 0.1,
  "alpha": 0.01,
  "beta": 0.05,
  "batch_size": 64,
  "max_samples": 1536,
  "evaluation_grid": [
    0.0,
    0.01,
    0.02,
    0.03,
    0.05,
    0.08,
    0.1,
    0.12,
    0.15,
    0.2
  ]
}
```

---

*Report generated automatically by experiment-report.py (v3)*
*E2E results source: exit-code-based JSON, not text-pattern matching*
