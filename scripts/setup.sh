#!/usr/bin/env bash
set -euo pipefail

# DDTM-QAS Development Environment Setup
# Run from project root: bash scripts/setup.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== DDTM-QAS Environment Setup ==="

# Check Go version
if command -v go &>/dev/null; then
    GO_VERSION=$(go version | grep -oP 'go\K[0-9]+\.[0-9]+')
    echo "Found Go: $GO_VERSION"
    if [[ "$(echo "$GO_VERSION < 1.25" | bc -l 2>/dev/null || echo 1)" == "1" ]]; then
        echo "WARNING: Go 1.25+ required for gnark 0.15. Please install Go 1.25."
        echo "  https://go.dev/dl/"
    fi
else
    echo "ERROR: Go not found. Please install Go 1.25+."
    exit 1
fi

# Check Rust
if command -v rustc &>/dev/null; then
    echo "Found Rust: $(rustc --version)"
else
    echo "WARNING: Rust not found. Install with: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
fi

# Check Foundry
if command -v forge &>/dev/null; then
    echo "Found Foundry: $(forge --version)"
else
    echo "WARNING: Foundry not found. Install with: curl -L https://foundry.paradigm.xyz | bash && foundryup"
fi

# Check Python
echo "Python: $(python3 --version)"

# Install Python dependencies
echo ""
echo "=== Installing Python dependencies ==="
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r ml/requirements.txt 2>/dev/null || echo "  pip install ml/requirements.txt failed (some packages may need compilation)"
pip install -q -r services/policy_optimizer/requirements.txt 2>/dev/null || echo "  pip install optimizer requirements failed"

# Setup Docker
if command -v docker &>/dev/null; then
    echo ""
    echo "=== Setting up Docker services ==="
    cp -n .env.example .env 2>/dev/null || true
    docker compose up -d postgres minio anvil 2>/dev/null || echo "  Docker services may already be running"
else
    echo "WARNING: Docker not found. PostgreSQL, MinIO, and Anvil will not be available."
fi

# Setup Contracts
if [ -d contracts ]; then
    echo ""
    echo "=== Setting up contracts ==="
    cd contracts
    if [ ! -d lib/openzeppelin-contracts ]; then
        forge install OpenZeppelin/openzeppelin-contracts --no-commit 2>/dev/null || echo "  forge install skipped (foundry may not be available)"
    fi
    cd "$ROOT"
fi

# Build
echo ""
echo "=== Building ==="
if command -v go &>/dev/null && [[ "$(go version | grep -oP 'go\K[0-9]+\.[0-9]+')" > "1.24" ]]; then
    make canonicalizer 2>/dev/null || echo "  canonicalizer build failed (go 1.25 required)"
    make zk-test 2>/dev/null || echo "  zk tests failed (go 1.25 required)"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. source .venv/bin/activate"
echo "  2. Verify Go 1.25: go version"
echo "  3. Build all: make all"
echo "  4. Run optimizer: make optimizer"
echo "  5. Run contract tests: make contracts-test"
