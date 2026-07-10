# Digest binding

The contract stores full 32-byte SHA-256 object digests. Circuits receive the digest reduced modulo the BN254 scalar field and include it in a context-specific public binding. Retaining the full digest avoids treating field reduction as the sole object identifier, while the reduced value permits efficient circuit composition.
