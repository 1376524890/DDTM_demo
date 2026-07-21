#!/usr/bin/env bash
set -euo pipefail

# DDTM-QAS Groth16 Multi-Party Ceremony (Phase 2) Coordinator Script
#
# This script documents the full MPC setup process for UtilityThreshold and
# AuditBatch circuits. The actual ceremony requires:
#   - Go 1.25+ with gnark 0.15
#   - At least 5 independent participants
#   - Secure communication channel for transcript transfer
#
# Usage:
#   Phase 1 (BN254 universal): Performed once per curve
#   Phase 2 (per-circuit):     bash scripts/ceremony.sh utility|audit

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CIRCUIT="${1:-}"
CEREMONY_DIR="${ROOT}/ceremony"

if [ -z "$CIRCUIT" ] || [ "$CIRCUIT" != "utility" ] && [ "$CIRCUIT" != "audit" ]; then
    echo "Usage: $0 <utility|audit>"
    echo ""
    echo "DDTM-QAS Groth16 Ceremony Coordinator"
    echo ""
    echo "Phase 1 (BN254 universal setup):"
    echo "  Requires separate gnark MPC tooling"
    echo ""
    echo "Phase 2 (per-circuit setup):"
    echo "  1. Coordinator publishes R1CS + initial contribution"
    echo "  2. Participant N downloads transcript, contributes, uploads"
    echo "  3. After all contributions, coordinator finalizes"
    exit 1
fi

mkdir -p "$CEREMONY_DIR/$CIRCUIT"

echo "============================================"
echo "DDTM-QAS Groth16 Ceremony: $CIRCUIT"
echo "============================================"
echo ""
echo "Step 0: Compile circuit and generate initial contribution"
echo ""

# Step 0: Coordinator compiles circuit and generates initial contribution.
cd "$ROOT/zk"

CIRCUIT_OUT="$CEREMONY_DIR/$CIRCUIT"
R1CS_FILE="$CIRCUIT_OUT/${CIRCUIT}.r1cs"
PHASE1_FILE="$CEREMONY_DIR/phase1.bin"

echo "R1CS output: $R1CS_FILE"
echo ""

# Publish R1CS hash for public verification.
echo "--- R1CS Digest ---"
if [ -f "$R1CS_FILE" ]; then
    sha256sum "$R1CS_FILE"
else
    echo "(R1CS not yet compiled — run: go run ./cmd/setup --circuit $CIRCUIT --out $CIRCUIT_OUT --unsafe-development-setup)"
fi

echo ""
echo "============================================"
echo "Participant Instructions"
echo "============================================"
echo ""
echo "Each participant (i = 1..N):"
echo ""
echo "  1. Download transport.zip from coordinator"
echo "  2. Verify R1CS hash:"
echo "     sha256sum $CIRCUIT.r1cs"
echo "  3. Run contribution:"
echo "     go run ./cmd/ceremony contribute \\"
echo "       --circuit $CIRCUIT \\"
echo "       --in transport-prev.zip \\"
echo "       --out transport-next.zip \\"
echo "       --entropy-source /dev/urandom"
echo "  4. Securely destroy local copy of transport-prev.zip"
echo "  5. Upload transport-next.zip to coordinator"
echo ""
echo "Verification (coordinator after each contribution):"
echo "  go run ./cmd/ceremony verify \\"
echo "    --circuit $CIRCUIT \\"
echo "    --in transport-next.zip"
echo ""
echo "Finalization (after N >= 5 participants):"
echo "  go run ./cmd/ceremony finalize \\"
echo "    --circuit $CIRCUIT \\"
echo "    --in transport-final.zip \\"
echo "    --out-pk ${CIRCUIT}.pk \\"
echo "    --out-vk ${CIRCUIT}.vk \\"
echo "    --out-solidity ${CIRCUIT}Verifier.sol"
echo ""
echo "Post-ceremony:"
echo "  1. Publish PK, VK, R1CS SHA-256 hash"
echo "  2. Deploy ${CIRCUIT}Verifier.sol"
echo "  3. Register verifier address + circuit hash in PolicyRegistry"
echo ""
echo "Security requirements:"
echo "  - Each participant MUST use an air-gapped machine (or at minimum,"
echo "    a fresh VM with no network during contribution)"
echo "  - Toxic waste (randomness) MUST be destroyed after contribution"
echo "  - At least ONE honest participant ensures soundness"
echo "  - Coordinator verifies every contribution before accepting"
