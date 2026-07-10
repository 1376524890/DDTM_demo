# V1 architecture decisions

- Hardhat is the reference EVM because gnark exports Ethereum-compatible BN254 verifiers and the environment is familiar to international reviewers.
- MinIO is used for deterministic local object storage; the storage adapter preserves a future S3/IPFS replacement boundary.
- PostgreSQL provides durable idempotency and event-index state rather than relying on in-memory orchestration.
- Proof generation is separated into a Go service so private witness material never enters Solidity or the public API response.
- AES-256-GCM and RSA-OAEP remain outside the circuit. Their exact object digests are bound into proof public inputs and contract events, while decryption failure is handled by the dispute path.
