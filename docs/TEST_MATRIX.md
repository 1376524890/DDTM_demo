# DDTM V1 verification matrix

| Layer | Evidence |
|---|---|
| ZKP relation correctness | gnark solving tests for valid and invalid witnesses |
| Proof serialization | 256-byte uncompressed BN254 Groth16 proof validation |
| EVM verification | generated Solidity verifier contracts exercised on Hardhat |
| Context replay defense | real proof from one listing rejected by a second listing |
| State-machine completeness | normal, invalid proof, timeout, dispute, arbitration, abort and withdrawal tests |
| Cross-module idempotency | PostgreSQL unique request key and on-chain requestId mapping |
| Storage integrity | MinIO SHA-256 metadata and read-time digest verification |
| Data confidentiality | AES-256-GCM payload encryption and RSA-OAEP key envelope tests |
| Event consistency | block/hash/parent index with rollback and replay on reorganization |
| Closed-loop execution | smoke script decrypts MinIO data and reaches CONFIRMED |
