#!/bin/bash
# DDTM Experiment Suite - Complete Reproduction
# ============================================

echo "============================================"
echo "DDTM v24 Experiment Suite"
echo "============================================"
echo ""

# Environment info
echo "=== Environment ==="
echo "CPU: $(grep 'model name' /proc/cpuinfo | head -1 | cut -d: -f2 | xargs)"
echo "Cores: $(nproc)"
echo "OS: $(uname -r)"
echo ""

# 1. ZKP Circuit Benchmarks (pre-compiled binaries)
echo "=== 1. ZKP Circuit Benchmarks ==="
echo ""
echo "--- pi_key_full + pi_deliver_byte (Groth16 BN254) ---"
if [ -f ./ddtm_v22 ]; then
    ./ddtm_v22 both 2>&1 | grep -E 'PASS|FAIL|Total|Compile|Setup|constraints|prove|verify'
else
    echo "  [SKIP] ddtm_v22 binary not found (pre-compiled)"
fi

echo ""
echo "--- ddtm_zkp benchmark ---"
if [ -f ./ddtm_zkp ]; then
    ./ddtm_zkp benchmark 2>&1 | grep -E 'Constraints|Prove|Verify|Setup|PK size|Proof size'
else
    echo "  [SKIP] ddtm_zkp binary not found (pre-compiled)"
fi

echo ""

# 2. π_Q Circuit (Go source - requires Go 1.25+)
echo "=== 2. π_Q Quality Proof Circuit ==="
if command -v go &> /dev/null; then
    echo "Go available: $(go version)"
    go build -o pi_q_bin pi_q.go 2>/dev/null && ./pi_q_bin || echo "  π_Q build failed (module deps needed)"
else
    echo "  [SKIP] Go not installed"
    echo "  Circuit design: pi_q.go (228 lines)"
    echo "  Design: 10-field MiMC hash + quality threshold + freshness + format validation"
    echo "  Projected: ~2,310 constraints, ~51ms prove (Groth16 BN254)"
fi

echo ""

# 3. Multi-Node Consortium Chain Simulation
echo "=== 3. Multi-Node Consortium Chain Simulation ==="
echo "  PBFT consensus, 4/7/10 nodes, 10/100/500 concurrent TX"
python3 multi_node_sim.py 2>&1 | grep -E 'Nodes=|Total'
echo ""

# 4. Experiment Data Report
echo "=== 4. Experiment Data Report ==="
python3 experiment_report.py 2>&1 | head -30
echo ""

echo "=== Complete ==="
echo "Experiment scripts: multi_node_sim.py, experiment_report.py, pi_q.go"
echo "Pre-compiled: ddtm_v22 (π_key+π_deliver), ddtm_zkp (benchmark)"
echo "Documentation: EXPERIMENT_README.md"
