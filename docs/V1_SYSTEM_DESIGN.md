# DDTM V1 system design

## Scope

DDTM V1 is an EVM reference implementation intended to demonstrate that the protocol described in the paper can execute as a closed, auditable workflow. It is not presented as a production data exchange. V1 uses Hardhat, Solidity, gnark Groth16 on BN254, PostgreSQL and MinIO.

## Components

- **DDTMProtocol** stores immutable commitments, escrow, deadlines, evidence hashes and final states.
- **Generated verifier contracts** verify `pi_Q`, `pi_deliver` and `pi_key` directly on the EVM.
- **Go prover service** owns circuit artifacts and exposes an HMAC-authenticated proof API.
- **Gateway/orchestrator** encrypts data, stores ciphertext, coordinates proof phases and submits transactions.
- **MinIO** stores AES-256-GCM ciphertexts, RSA-OAEP key envelopes and evidence objects.
- **PostgreSQL** stores encrypted private witness material, request idempotency records and a reorg-aware event index.

## End-to-end sequence

1. The seller submits four fixed-format records and a payload to the gateway.
2. The gateway creates independent commitment randomness, a data key and per-block circuit randomness.
3. The payload is encrypted with AES-256-GCM and uploaded to MinIO. SHA-256 of the exact stored envelope is recorded on-chain.
4. The prover derives `cD`, `cQ`, `cK` and the circuit delivery root. The seller calls `list` and locks a 10 percent bond.
5. The buyer locks payment and registers a buyer-key field derived from its RSA public key.
6. `pi_Q` computes the completeness count from the committed records, checks field ranges and freshness, and binds the proof to the transaction context.
7. `pi_deliver` proves the committed data/key relationship and the circuit-friendly encrypted Merkle root. Its public binding includes the MinIO object digest and transaction context.
8. The gateway creates an RSA-OAEP envelope containing the actual AES key and stores it in MinIO. `pi_key` proves the key commitment and buyer/context binding; its public binding includes the exact envelope digest.
9. The buyer downloads both objects, opens the RSA envelope, decrypts the AES-GCM ciphertext and either confirms or opens a dispute.
10. Confirmation releases escrow to the seller. A dispute freezes settlement and binds evidence objects to an arbitrator decision.

## Engineering split for delivery verification

V1 does not put AES-256-GCM or RSA-OAEP inside the arithmetic circuit. Doing so would substantially increase constraints without improving the main protocol experiment. The system therefore separates:

- a circuit-friendly MiMC root proving the committed data/key relation;
- a SHA-256 digest proving which exact MinIO object the seller signed and delivered;
- buyer-side AES-GCM authentication and commitment rechecking;
- dispute and bond paths for an invalid real-world ciphertext or key envelope.

This implements the engineering mode described in the paper. It provides weak fair exchange rather than claiming that the EVM circuit alone proves every bit of an AES ciphertext.

## Message and proof formats

The public HTTP API uses JSON and requires `Idempotency-Key`. Internal prover requests are canonical JSON authenticated as:

```text
HMAC-SHA256(shared_secret, unix_timestamp || "." || canonical_json_body)
```

Groth16 proofs use gnark's uncompressed Solidity format:

```text
Ar.X | Ar.Y | Bs.X1 | Bs.X0 | Bs.Y1 | Bs.Y0 | Krs.X | Krs.Y
```

Each field element occupies 32 bytes, for a 256-byte proof. Public inputs are decimal BN254 field elements in the exact order defined by the generated verifier.

## Context and replay protection

The contract derives the proof context from:

```text
keccak256(tid, chainId, contractAddress, contractHash, seller, buyer, nonce) mod Fr
```

Every proof includes this value. Each mutating API call also maps its idempotency key to a deterministic `bytes32 requestId`; the contract rejects a request ID that was already consumed.

## Event processing and chain reorganization

The indexer records block number, hash, parent hash, transaction hash and log index. Before accepting a block it checks both the stored hash at that height and the previous canonical parent. On a mismatch it deletes affected events and blocks, rewinds the checkpoint and replays canonical logs. Hardhat normally has one-block local finality, but the indexer implements the same rollback mechanism needed for later public-EVM deployment.

## Service authentication

- Public V1 API: bearer/API key for the closed research deployment.
- Gateway-to-prover: timestamped HMAC with a one-minute replay window.
- Blockchain authority: separate seller, buyer and arbitrator ECDSA accounts.
- Stored private witness: AES-256-GCM encrypted before insertion into PostgreSQL.

For a production consortium deployment these controls should be replaced or supplemented by mTLS, institution certificates, a KMS/HSM and per-organization authorization.

## Reproducibility

- `make setup-zkp` compiles circuits, runs Groth16 setup and exports Solidity verifiers.
- `make test-v1` executes circuit tests, mock-verifier state-machine tests, real-proof Hardhat tests and gateway tests.
- `docker compose up --build -d` starts the complete stack.
- `make smoke` performs listing, escrow, all three proofs, MinIO retrieval, RSA/AES decryption and final confirmation.
