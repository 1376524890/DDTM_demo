#!/usr/bin/env bash
# Run G0 and G1 in release mode and emit the combined final report.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Regenerating G0 (release: requires CLEAN tree) ==="
python3 -m experiments.g0.report \
  --config experiments/configs/g0-default.json \
  --release \
  --output experiments/raw/g0-result.json \
  --report experiments/reports/g0-report.md

echo "=== Running G1 pipeline ==="
bash scripts/run-g1.sh

echo "=== Writing combined final report ==="
python3 -m experiments.report_final \
  --output experiments/reports/final-report.md

echo "=== Final report: experiments/reports/final-report.md ==="
