# Reviewer execution path

For source-level verification, run `make test-v1`. For full system verification, run `docker compose up --build -d` and `make smoke`. The smoke test reports success only after the buyer retrieves MinIO artifacts, opens the RSA-OAEP key envelope, authenticates and decrypts the AES-GCM ciphertext, and the contract reaches `CONFIRMED`.
