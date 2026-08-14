#!/usr/bin/env bash
# VALOR 一键复现：全流程交易 + 参数扫描实验（Phase 8）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY=.venv/bin/python
echo "==> 全流程交易"
$PY -m valor transaction run --config configs/experiments/full_transaction.json
echo "==> 参数扫描实验"
$PY -m valor experiment run --config configs/experiments/sweep.json
echo "==> 测试"
$PY -m pytest -q
