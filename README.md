# DDTM-QAS Prototype

DDTM-QAS is a research prototype for privacy-preserving data trading with three tightly coupled mechanisms:

1. **ARUC** - attested robust utility certification inside a confidential VM.
2. **ZASA** - zero-knowledge adaptive semantic audit over a Poseidon2 Merkle commitment.
3. **JABO** - joint audit/bond optimization for incentive-compatible settlement.

The reference task is tabular binary classification with up to 100,000 rows and 128 fixed-point features. Model architecture is public; model parameters and the buyer validation set remain private.

## Security boundary

- Full private evaluation runs inside Intel TDX or AMD SEV-SNP. The local development backend is a mock and does **not** provide hardware confidentiality.
- Groth16 proves threshold relations and sampled audit computations. It does not prove the complete 100,000-row MLP evaluation.
- A single Poseidon2 Merkle root binds listing, evaluation, audit, delivery, and disputes.
- Delivery uses XChaCha20-Poly1305. The buyer recomputes the entire Merkle root after decryption.
- drand supplies future, publicly verifiable sampling randomness.

## Repository map

- `specs/`: frozen protocol, encoding, threat model, and state-machine specifications.
- `canonicalizer-go/`: deterministic row codec and Poseidon2 Merkle builder.
- `tee-evaluator-rust/`: fixed-point MLP utility evaluator and audit witness service.
- `zk/`: gnark Groth16 circuits for utility thresholds and audit batches.
- `contracts/`: Solidity registries and marketplace state machine.
- `services/policy_optimizer/`: exact/Monte-Carlo optimization of audit and bond parameters.
- `ml/`: model training and data preparation utilities.

## Required versions

- Ubuntu 24.04 LTS
- Go 1.25+
- gnark 0.15.0
- gnark-crypto 0.20.1
- Rust stable 1.88+
- Python 3.11+
- Foundry current stable
- Docker Engine 27+

## Development bring-up

```bash
cp .env.example .env
docker compose up -d postgres minio anvil
python -m venv .venv
source .venv/bin/activate
pip install -r services/policy_optimizer/requirements.txt
python services/policy_optimizer/optimizer.py --config experiments/configs/policy-default.json
```

Then install Go 1.25 and build the canonicalizer and circuits:

```bash
make canonicalizer
make zk-test
```

Build the evaluator:

```bash
make evaluator
```

Deploy contracts:

```bash
cd contracts
forge install OpenZeppelin/openzeppelin-contracts --no-commit
forge test
```

## Non-negotiable protocol invariants

1. Buyer model/validation commitments must be posted before the seller dataset root is revealed to the evaluator.
2. Every proof and attestation binds `chain_id`, `contract`, `transaction_id`, `policy_hash`, and a monotonic session nonce.
3. Audit indices derive from a future drand round committed before its publication.
4. Audit sampling never substitutes for full delivery identity; the buyer always recomputes the complete root.
5. `INCONCLUSIVE` is never interpreted as `PASS`.
6. Groth16 development setup artifacts must never be reused for a public deployment.

See `specs/protocol.md` and the two delivered design documents for the exact execution sequence.
