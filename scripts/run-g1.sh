#!/usr/bin/env bash
# Run the full G1 cross-language pipeline: generate vectors (Python golden),
# then independently verify with Go, Rust and gnark, then run the gate.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== G1: generate canonical vectors (Python golden) ==="
python3 -m experiments.g1.generate_vectors

echo "=== G1: Go verifier ==="
( cd canonicalizer-go && go run ./cmd/verify-vectors \
    --manifest ../experiments/vectors/manifest.json \
    --output ../experiments/raw/g1-go.json )

echo "=== G1: Rust verifier ==="
# The bin resolves the repo root by walking up from its cwd.
( cd tee-evaluator-rust && cargo run --release --bin verify-vectors )

echo "=== G1: gnark in-circuit verifier ==="
( cd zk && go test ./tests -run TestGnarkVerifyVectors -timeout 300s )

echo "=== G1: cross-language gate ==="
python3 -m experiments.g1.gate \
  --manifest experiments/vectors/manifest.json \
  --go experiments/raw/g1-go.json \
  --rust experiments/raw/g1-rust.json \
  --gnark experiments/raw/g1-gnark.json \
  --output experiments/raw/g1-gate.json
echo "G1: DONE"
