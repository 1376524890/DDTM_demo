# Transaction context binding

The context is derived only after a buyer is fixed. It includes the listing-derived transaction ID, chain ID, contract address, contract hash, seller, buyer and nonce, then is reduced into the BN254 scalar field. Quality, delivery and key proofs all use the same context, so a valid proof cannot be copied to another listing, buyer or contract.
