# DDTM-QAS Protocol v1

## Phase 0 - Policy publication

Governance publishes a `PolicyRecord` containing circuit hashes, verifier addresses, data schema, utility thresholds, audit SPRT parameters, economic parameters, approved TEE measurements, and a policy hash.

## Phase 1 - Buyer precommitment

The buyer trains the public 128-64-1 model architecture and private linear audit probe, canonicalizes the private validation set, and publishes commitments `c_M`, `c_V`, and `c_A` before evaluation.

## Phase 2 - Seller listing

The seller canonicalizes the dataset, builds Poseidon2 root `c_D`, computes SHA-256 object digests, deposits the JABO-required bond, and selects a future drand round.

## Phase 3 - Attested utility evaluation

After remote attestation, seller and buyer derive separate X25519 session keys and upload encrypted inputs. The evaluator verifies all commitments, computes ARUC metrics over the full data, signs a report, and emits the private witness for the UtilityThreshold Groth16 proof.

## Phase 4 - ZASA audit

After the committed drand round becomes available and is verified, deterministic non-repeating indices are generated. The evaluator constructs batches of rows and Merkle paths. Each AuditBatch proof validates membership, the committed audit probe, semantic scores, counters, and the sequential state transition. The contract accepts, rejects, or marks the transaction inconclusive.

## Phase 5 - Encrypted delivery

The seller encrypts the canonical binary dataset in 8 MiB chunks using XChaCha20-Poly1305 and commits the manifest digest. The data key is encapsulated to the buyer. The buyer decrypts and recomputes the entire Poseidon2 root.

## Phase 6 - Settlement or dispute

A matching root permits confirmation. A mismatch dispute sends the chain-bound ciphertext, manifest, and key to a fresh attested evaluator, which emits a signed delivery receipt. The contract settles according to the receipt or timeout rules.
