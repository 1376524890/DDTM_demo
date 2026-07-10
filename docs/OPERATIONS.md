# Local operations

- `docker compose ps` reports service health.
- `docker compose logs -f gateway prover hardhat` follows protocol activity.
- `docker compose down` stops the stack while retaining state.
- `docker compose down -v` removes PostgreSQL, MinIO, proving keys, generated verifiers and deployment state.
- The MinIO console is exposed on port 9001 and the gateway on port 8080.

The local stack is intentionally deterministic. Do not expose its ports to an untrusted network.
