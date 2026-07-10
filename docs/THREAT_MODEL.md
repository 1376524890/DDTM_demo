# V1 threat model mapping

- Data or commitment replacement: commitment and verifier checks.
- Cross-order proof replay: transaction context and on-chain request IDs.
- Buyer refusal to pay: escrow before proof and delivery phases.
- Seller refusal to prove or release a key: bounded timeout refunds and bond transfer.
- Invalid storage object: exact SHA-256 digest on-chain, authenticated decryption and dispute evidence.
- Duplicate service requests: PostgreSQL body-bound idempotency plus contract request consumption.
- Event duplication or chain reorganization: unique log identity, block-parent tracking, rollback and replay.
- Unauthorized arbitration: configured arbitrator address.

V1 does not automatically prevent post-delivery copying, colluding arbitration or semantic-quality misrepresentation; these remain governance and audit concerns.
