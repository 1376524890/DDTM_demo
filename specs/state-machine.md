# State Machine v1

`LISTED -> ESCROWED -> TEE_REGISTERED -> UTILITY_VERIFIED -> AUDITING`

Audit outcomes:

- `AUDIT_ACCEPTED -> CIPHERTEXT_COMMITTED -> KEY_RELEASED -> BUYER_CHECKING -> CONFIRMED`
- `AUDIT_REJECTED -> REFUNDED`
- `AUDIT_INCONCLUSIVE -> CONDITIONAL` and buyer explicitly accepts higher residual risk or exits after paying incurred audit cost.

Delivery disputes:

- `BUYER_CHECKING -> DISPUTED -> RESOLVED_SELLER | RESOLVED_BUYER`

Every transition consumes a unique request ID and checks a deadline.
