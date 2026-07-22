#!/usr/bin/env bash
# DDTM-QAS End-to-End Integration Test (v2)
# Exit-code based: every step is evaluated by exit code, not text matching.
# Generates a JSON results file for downstream consumption.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RESULTS_DIR="${ROOT}/experiments/results"
mkdir -p "$RESULTS_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RESULTS_FILE="${RESULTS_DIR}/e2e_results_${TIMESTAMP}.json"

# Initialize results array.
results_json='{"timestamp": "'"${TIMESTAMP}"'", "tests": []}'

# ------------------------------------------------------------------
# Helper: run a test step, capture exit code, append JSON record.
# Usage: run_test <test_name> <expected_unique> <command...>
# ------------------------------------------------------------------
run_test() {
    local test_name="$1"
    local expected_unique="${2:-0}"
    shift 2

    local actual_unique=0
    local exit_code=0
    local output=""

    # Run command; capture stdout+stderr and exit code.
    if output=$("$@" 2>&1); then
        exit_code=0
    else
        exit_code=$?
    fi

    # Try to extract a count from output (for permutation tests).
    # Matches: "N unique", "N/N passed", "N/N verified"
    if echo "$output" | grep -qP '(\d+)\s*(?:unique|/\d+\s*(?:passed|verified))'; then
        actual_unique=$(echo "$output" | grep -oP '(\d+)\s*(?=unique|/\d+\s*(?:passed|verified))' | head -1)
    fi

    local status="passed"
    if [[ "$exit_code" -ne 0 ]]; then
        status="failed"
    fi

    # Build JSON entry.
    local json_entry
    json_entry=$(jq -n \
        --arg name "$test_name" \
        --arg status "$status" \
        --argjson expected "$expected_unique" \
        --argjson actual "$actual_unique" \
        --argjson exit "$exit_code" \
        '{test_name: $name, status: $status, expected_unique: $expected, actual_unique: $actual, exit_code: $exit}')

    # Append to results file.
    results_json=$(echo "$results_json" | jq ".tests += [${json_entry}]")

    # Print to terminal.
    if [[ "$status" == "passed" ]]; then
        echo "[PASS] ${test_name} (exit=${exit_code})"
    else
        echo "[FAIL] ${test_name} (exit=${exit_code})"
    fi
    if [[ -n "$output" ]]; then
        echo "$output" | head -20
    fi
}

# ------------------------------------------------------------------
# Step 0: Environment Checks
# ------------------------------------------------------------------
echo "=== Step 0: Environment Checks ==="

run_test "python3_available" 0 python3 --version
run_test "go_available" 0 go version
run_test "rustc_available" 0 rustc --version

# ------------------------------------------------------------------
# Step 1: Policy Optimizer
# ------------------------------------------------------------------
echo ""
echo "=== Step 1: JABO Policy Optimization ==="

run_test "jabo_policy_optimization" 0 \
    python3 services/policy_optimizer/optimizer.py \
        --config experiments/configs/policy-default.json \
        --output experiments/policy-default-result.json

# Verify key numeric results against expected values.
if [[ -f experiments/policy-default-result.json ]]; then
    run_test "sprt_detection_probability" 0 python3 -c "
import json
r = json.load(open('experiments/policy-default-result.json'))
d = r['bad_quality_detection_probability']
assert abs(d - 0.951215) < 0.001, f'Detection mismatch: {d}'
print(f'Detection probability: {d} (target: 0.951215)')
"

    run_test "jabo_minimum_bond" 0 python3 -c "
import json
r = json.load(open('experiments/policy-default-result.json'))
b = r['minimum_bond']
assert abs(b - 3141.09) < 1.0, f'Bond mismatch: {b}'
print(f'Minimum bond: {b} (target: 3141.09)')
"
fi

# ------------------------------------------------------------------
# Step 2: Cross-Test Vectors
# ------------------------------------------------------------------
echo ""
echo "=== Step 2: Cross-Test Vectors ==="

run_test "cross_test_vectors" 0 python3 experiments/cross_test_poseidon.py

# ------------------------------------------------------------------
# Step 3: SPRT Boundary Verification
# ------------------------------------------------------------------
echo ""
echo "=== Step 3: SPRT Boundary Verification ==="

run_test "sprt_boundaries" 0 python3 -c "
import math
tau0, tau1, alpha, beta = 0.05, 0.10, 0.01, 0.05
lower = math.log(beta / (1 - alpha))
upper = math.log((1 - beta) / alpha)
print(f'SPRT lower={lower:.6f} (paper: -2.985682)')
print(f'SPRT upper={upper:.6f} (paper: 4.553877)')
assert abs(lower - (-2.9856819377004893)) < 0.0001
assert abs(upper - 4.553876891600541) < 0.0001
print('SPRT boundaries verified')
"

# ------------------------------------------------------------------
# Step 4: Feistel17 Permutation (real Go test)
# ------------------------------------------------------------------
echo ""
echo "=== Step 4: Feistel17 Permutation ==="

run_test "feistel17_permutation" 131072 \
    go test -C zk -v -run "TestFeistel17Native$" ./circuits/ -timeout 120s

run_test "feistel17_inverse_roundtrip" 131072 \
    go test -C zk -v -run "TestFeistel17InverseRoundTrip$" ./circuits/ -timeout 120s

run_test "feistel17_multi_seed" 0 \
    go test -C zk -v -run "TestFeistel17MultiSeed$" ./circuits/ -timeout 120s

# ------------------------------------------------------------------
# Step 5: Foundry Environment
# ------------------------------------------------------------------
echo ""
echo "=== Step 5: Foundry Environment ==="

FOUNDRY_BIN="${HOME}/.foundry/bin"
if [[ -x "${FOUNDRY_BIN}/forge" ]]; then
    run_test "foundry_forge" 0 "${FOUNDRY_BIN}/forge" --version
else
    echo "[SKIP] Foundry forge not found at ${FOUNDRY_BIN}/forge"
    results_json=$(echo "$results_json" | jq '.tests += [{"test_name":"foundry_forge","status":"failed","expected_unique":0,"actual_unique":0,"exit_code":127}]')
fi

if [[ -x "${FOUNDRY_BIN}/anvil" ]]; then
    run_test "foundry_anvil" 0 "${FOUNDRY_BIN}/anvil" --version
else
    echo "[SKIP] Foundry anvil not found at ${FOUNDRY_BIN}/anvil"
    results_json=$(echo "$results_json" | jq '.tests += [{"test_name":"foundry_anvil","status":"failed","expected_unique":0,"actual_unique":0,"exit_code":127}]')
fi

if [[ -x "${FOUNDRY_BIN}/cast" ]]; then
    run_test "foundry_cast" 0 "${FOUNDRY_BIN}/cast" --version
else
    echo "[SKIP] Foundry cast not found at ${FOUNDRY_BIN}/cast"
    results_json=$(echo "$results_json" | jq '.tests += [{"test_name":"foundry_cast","status":"failed","expected_unique":0,"actual_unique":0,"exit_code":127}]')
fi

# ------------------------------------------------------------------
# Step 6: Data Preparation
# ------------------------------------------------------------------
echo ""
echo "=== Step 6: Data Preparation ==="

run_test "data_preparation" 0 python3 -c "
import numpy as np
from pathlib import Path
Path('data/raw').mkdir(parents=True, exist_ok=True)
n = 20000; d = 128
rng = np.random.default_rng(20260721)
x = rng.normal(0, 1, (n, d)).astype(np.float32)
y = np.where(x[:, 0] + x[:, 1] > 0, 1, -1).astype(np.int8)
np.savez_compressed('data/raw/synthetic.npz', x=x, y=y)
print(f'Generated {n} x {d} synthetic data')
"

# ------------------------------------------------------------------
# Write final results
# ------------------------------------------------------------------
echo "$results_json" | jq '.' > "$RESULTS_FILE"

# Count pass/fail.
PASS=$(echo "$results_json" | jq '[.tests[] | select(.status == "passed")] | length')
FAIL=$(echo "$results_json" | jq '[.tests[] | select(.status == "failed")] | length')

echo ""
echo "=========================================="
echo "E2E Test Results: ${PASS} passed, ${FAIL} failed"
echo "Results saved to: ${RESULTS_FILE}"
echo "=========================================="

if [[ "$FAIL" -eq 0 ]]; then
    echo "All tests passed!"
    exit 0
else
    echo "Some tests failed. See JSON report for details."
    exit 1
fi
