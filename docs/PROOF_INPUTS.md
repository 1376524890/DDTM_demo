# V1 proof public inputs

All values are BN254 scalar-field elements in the listed order.

- `pi_Q`: `cD, cQ, minPresent, maxValue, maxAge, asOfTime, context, binding`
- `pi_deliver`: `cD, cK, zkRoot, objectDigestField, context, binding`
- `pi_key`: `cK, buyerKey, keyEnvelope, envelopeDigestField, context, binding`

`objectDigestField` and `envelopeDigestField` are the respective SHA-256 values reduced modulo the BN254 scalar field. The full 32-byte digests remain in contract state and events.
