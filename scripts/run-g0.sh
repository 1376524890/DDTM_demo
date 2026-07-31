#!/usr/bin/env bash
# Regenerate the G0 statistical/economic baseline report.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== G0: statistical & economic baseline ==="
python3 -m experiments.g0.report \
  --config experiments/configs/g0-default.json \
  --output experiments/raw/g0-result.json \
  --report experiments/reports/g0-report.md

echo "=== G0 tests ==="
python3 -m pytest -q experiments/tests/test_g0.py
echo "G0: DONE"
