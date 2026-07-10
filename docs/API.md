# DDTM V1 HTTP API

Base URL: `http://localhost:8080`

All `/v1` routes require:

```text
X-DDTM-API-Key: <configured key>
```

Every mutating request also requires a stable client-generated key:

```text
Idempotency-Key: <8-128 ASCII characters>
```

Reusing a key with the same operation and body returns the stored response. Reusing it with a different body returns HTTP 409. The same logical key is converted into phase-specific on-chain `requestId` values, so duplicate calls are rejected by both PostgreSQL and the contract.

## Health

```http
GET /health
```

## Create a listing

```http
POST /v1/listings
Content-Type: application/json
```

```json
{
  "records": [
    {"value":"10","timestamp":"1710000000","present":"1"},
    {"value":"20","timestamp":"1710000010","present":"1"}
  ],
  "payload": {"dataset":"example"},
  "priceWei":"1000000000000000000",
  "minPresent":"2",
  "maxValue":"100",
  "maxAge":"3600",
  "asOfTime":"1710000100",
  "contractTerms":{"purpose":"research"}
}
```

The response contains `chainListingId`, `tid`, the four commitments, MinIO object metadata and the listing transaction hash.

## Lock buyer escrow

```http
POST /v1/listings/{id}/bids
```

```json
{"buyerPublicKeyPem":"-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n"}
```

The buyer public key is used for the RSA-OAEP envelope. A digest-derived BN254 field value is also bound into `pi_key`.

## Generate and submit all proofs

```http
POST /v1/listings/{id}/proofs
Content-Type: application/json

{}
```

The orchestrator reads the current contract state and executes only missing phases. It submits `pi_Q`, `pi_deliver`, then the key envelope and `pi_key`.

## Retrieve encrypted artifacts

```http
GET /v1/listings/{id}/artifacts/ciphertext
GET /v1/listings/{id}/artifacts/key-envelope
```

The gateway verifies the SHA-256 digest before returning each MinIO object. Short-lived presigned links are also available from:

```http
GET /v1/listings/{id}/downloads
```

## Confirm

```http
POST /v1/listings/{id}/confirm
Content-Type: application/json

{}
```

## Open and resolve a dispute

```http
POST /v1/listings/{id}/disputes
```

```json
{"evidence":{"type":"INVALID_KEY","details":"AES-GCM authentication failed"}}
```

```http
POST /v1/listings/{id}/disputes/resolve
```

```json
{
  "sellerWins":false,
  "decision":{"reason":"submitted key envelope did not open the committed data"}
}
```

The second route submits with the configured arbitrator account.

## Query state

```http
GET /v1/listings
GET /v1/listings/{id}
```
