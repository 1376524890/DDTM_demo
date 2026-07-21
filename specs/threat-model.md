# DDTM-QAS Threat Model v1

## Adversaries

The seller may misreport utility, submit poisoned data, selectively prepare audited rows, replace evaluated data before delivery, replay proofs, or abort after learning buyer information. The buyer may submit a malicious evaluation policy, falsely claim delivery mismatch, or withhold confirmation. The host administrator, object store, relays, and a Byzantine minority of blockchain nodes may be malicious.

## Trust assumptions

1. Intel TDX or AMD SEV-SNP remote attestation and memory isolation remain secure for the deployed TCB.
2. At least one Groth16 ceremony participant destroys its toxic waste.
3. Poseidon2, SHA-256, X25519/HKDF-SHA256, XChaCha20-Poly1305, secp256k1, and BN254 Groth16 satisfy their standard assumptions.
4. The selected drand beacon has fewer than its threshold number of colluding participants.
5. Model and validation commitments precede seller-data evaluation.
6. The platform defines a conservative finite upper bound `G_max` on one-transaction cheating gains.

## Out of scope

- Complete prevention of microarchitectural TEE side channels.
- Availability against denial of service.
- Absolute semantic truth where no trustworthy labels or task objective exist.
- Deterrence when cheating gains are unbounded or the seller has no collectible stake.
