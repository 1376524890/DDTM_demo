# Trusted setup status

V1 generates fresh Groth16 keys locally to make every artifact build self-contained. This is appropriate for protocol execution tests, not for a production trust claim. A deployment intended to protect real assets must use a documented multiparty ceremony, publish circuit and key hashes, and prevent obsolete verifying keys from authorizing new transactions.
