# Known limitations

- The reference chain is a single local Hardhat node, not a physical multi-node consortium deployment.
- Trusted setup is generated locally for reproducibility; a production Groth16 deployment requires a governed ceremony and versioned keys.
- The API uses one configured seller, buyer and arbitrator account.
- AES and RSA are not implemented inside the ZKP circuit; exact storage digests, buyer verification and disputes complete the weak-fairness design.
- Semantic data quality remains an evidence and arbitration question rather than an arithmetic-circuit claim.
