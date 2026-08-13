#!/usr/bin/env bash
# ============================================================
# VALOR-v1 一键复现脚本
# 运行完整实验管线并生成报告
# 用法: bash scripts/run-valor.sh [--config <path>]
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CONFIG="configs/lab-default.json"
if [[ "${1:-}" == "--config" && -n "${2:-}" ]]; then
  CONFIG="$2"
elif [[ -n "${1:-}" && "$1" != "--config" ]]; then
  CONFIG="$1"
fi

echo "=== VALOR-v1 管线开始 ==="
echo "配置: $CONFIG"

# 1. 校验配置（Phase 0 gate：缺失参数报错）
python3 -m valor.report check-config "$CONFIG"

# 2. 运行管线（后续阶段逐步填充）
python3 -m valor.report run --config "$CONFIG"

echo "=== 完成 ==="
