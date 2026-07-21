#!/usr/bin/env bash
set -euo pipefail

# DDTM-QAS Development Deployment Script
# Deploys all contracts to local Anvil chain and initializes registries.

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/contracts"

RPC="${ANVIL_RPC_URL:-http://127.0.0.1:8545}"
PRIVATE_KEY="${ANVIL_PRIVATE_KEY:-0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80}"

echo "=== Deploying DDTM-QAS to $RPC ==="

# Deploy PolicyRegistry
POLICY_ADDR=$(forge create --rpc-url "$RPC" --private-key "$PRIVATE_KEY" \
  src/PolicyRegistry.sol:PolicyRegistry \
  --constructor-args 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 \
  | tee /dev/stderr | grep "Deployed to" | awk '{print $3}')
echo "PolicyRegistry: $POLICY_ADDR"

# Deploy RandomnessRegistry
RANDOM_ADDR=$(forge create --rpc-url "$RPC" --private-key "$PRIVATE_KEY" \
  src/RandomnessRegistry.sol:RandomnessRegistry \
  --constructor-args 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 \
  "$(cast --to-hex 3)" \
  | tee /dev/stderr | grep "Deployed to" | awk '{print $3}')
echo "RandomnessRegistry: $RANDOM_ADDR"

# Deploy AttestationRegistry
ATTEST_ADDR=$(forge create --rpc-url "$RPC" --private-key "$PRIVATE_KEY" \
  src/AttestationRegistry.sol:AttestationRegistry \
  --constructor-args 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 \
  "$POLICY_ADDR" "$(cast --to-hex 3)" \
  | tee /dev/stderr | grep "Deployed to" | awk '{print $3}')
echo "AttestationRegistry: $ATTEST_ADDR"

# Deploy DDTMMarketplace
MARKET_ADDR=$(forge create --rpc-url "$RPC" --private-key "$PRIVATE_KEY" \
  src/DDTMMarketplace.sol:DDTMMarketplace \
  --constructor-args "$POLICY_ADDR" "$ATTEST_ADDR" "$RANDOM_ADDR" \
  | tee /dev/stderr | grep "Deployed to" | awk '{print $3}')
echo "DDTMMarketplace: $MARKET_ADDR"

echo "=== Deployment complete ==="
echo "Addresses:"
echo "  PolicyRegistry:     $POLICY_ADDR"
echo "  RandomnessRegistry: $RANDOM_ADDR"
echo "  AttestationRegistry: $ATTEST_ADDR"
echo "  DDTMMarketplace:    $MARKET_ADDR"
