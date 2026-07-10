# Stored artifact formats

## Ciphertext object

The MinIO ciphertext object is a UTF-8 JSON envelope:

```json
{
  "version": 1,
  "algorithm": "AES-256-GCM",
  "iv": "base64",
  "tag": "base64",
  "ciphertext": "base64"
}
```

The SHA-256 digest covers these exact bytes.

## Key envelope

The key-envelope object is raw RSA-OAEP ciphertext. OAEP and MGF1 use SHA-256. The plaintext is the 32-byte AES key derived from the committed scalar key.

## Evidence

Evidence objects are canonical UTF-8 JSON. Their SHA-256 digest and the Keccak hash of the MinIO URI are submitted to the contract.
