# Reproducibility checklist

1. Copy `.env.example` to `.env`.
2. Run `make test-v1` for source-level circuit, EVM and gateway tests.
3. Run `docker compose up --build -d` for the integrated stack.
4. Wait for `docker compose ps` to report healthy services.
5. Run `make smoke` to exercise MinIO encryption, escrow, all proofs, decryption and confirmation.
6. Preserve `ddtm_zkp/artifacts/v1/manifest.json`, CI logs, contract deployment manifest and gas output with the paper artifact.
