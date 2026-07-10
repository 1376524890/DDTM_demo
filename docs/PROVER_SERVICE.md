# Prover service boundary

The prover accepts at most one MiB of canonical JSON, verifies a timestamped HMAC and invokes a fixed local proof binary with a two-minute deadline. It returns commitments, the 256-byte proof, ordered public inputs and the public binding. Invalid witnesses return an error and never reach the blockchain adapter.
