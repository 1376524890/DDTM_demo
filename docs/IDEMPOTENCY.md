# Two-layer idempotency

The gateway stores each client `Idempotency-Key` with operation name and canonical request hash. A repeated matching request returns the saved result; a different request using the same key is rejected. Each logical operation also derives a deterministic on-chain request ID. The contract consumes that ID before executing the transition, preventing duplicate effects if an HTTP retry reaches the chain twice.
