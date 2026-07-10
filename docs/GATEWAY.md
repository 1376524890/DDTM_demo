# Gateway responsibilities

The gateway is an untrusted protocol coordinator: it prepares encrypted objects, requests proofs, submits actor-specific transactions, stores encrypted witness state and exposes audit-friendly APIs. It cannot bypass Solidity verifier checks, forge another configured actor's ECDSA transaction or alter a terminal contract state.
