#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${DDTM_BASE_URL:-http://127.0.0.1:8080}"
API_KEY="${GATEWAY_API_KEY:-ddtm-v1-local-api-key}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

for _ in $(seq 1 90); do
  if curl -fsS "$BASE_URL/health" >/dev/null; then
    break
  fi
  sleep 2
done
curl -fsS "$BASE_URL/health" | tee "$TMP/health.json"

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$TMP/buyer-private.pem" 2>/dev/null
openssl pkey -in "$TMP/buyer-private.pem" -pubout -out "$TMP/buyer-public.pem" 2>/dev/null

NOW="$(date +%s)"
cat >"$TMP/listing.json" <<JSON
{
  "records": [
    {"value":"10","timestamp":"$((NOW-30))","present":"1"},
    {"value":"20","timestamp":"$((NOW-20))","present":"1"},
    {"value":"30","timestamp":"$((NOW-10))","present":"1"}
  ],
  "payload": {"name":"DDTM V1 smoke dataset","purpose":"artifact validation"},
  "priceWei": "1000000000000000000",
  "minPresent": "3",
  "maxValue": "100",
  "maxAge": "300",
  "asOfTime": "$NOW",
  "contractTerms": {"purpose":"research","usage":"single-buyer"}
}
JSON

curl -fsS -X POST "$BASE_URL/v1/listings" \
  -H "x-ddtm-api-key: $API_KEY" \
  -H "Idempotency-Key: smoke-listing-001" \
  -H "content-type: application/json" \
  --data-binary @"$TMP/listing.json" | tee "$TMP/listing-response.json"

LISTING_ID="$(node -e "const x=require(process.argv[1]);process.stdout.write(String(x.chainListingId))" "$TMP/listing-response.json")"
node -e 'const fs=require("fs"); fs.writeFileSync(process.argv[2], JSON.stringify({buyerPublicKeyPem:fs.readFileSync(process.argv[1],"utf8")}))' \
  "$TMP/buyer-public.pem" "$TMP/bid.json"

curl -fsS -X POST "$BASE_URL/v1/listings/$LISTING_ID/bids" \
  -H "x-ddtm-api-key: $API_KEY" \
  -H "Idempotency-Key: smoke-bid-001" \
  -H "content-type: application/json" \
  --data-binary @"$TMP/bid.json" | tee "$TMP/bid-response.json"

curl -fsS -X POST "$BASE_URL/v1/listings/$LISTING_ID/proofs" \
  -H "x-ddtm-api-key: $API_KEY" \
  -H "Idempotency-Key: smoke-proofs-001" \
  -H "content-type: application/json" \
  --data '{}' | tee "$TMP/proofs-response.json"

curl -fsS "$BASE_URL/v1/listings/$LISTING_ID/artifacts/ciphertext" \
  -H "x-ddtm-api-key: $API_KEY" -o "$TMP/ciphertext.json"
curl -fsS "$BASE_URL/v1/listings/$LISTING_ID/artifacts/key-envelope" \
  -H "x-ddtm-api-key: $API_KEY" -o "$TMP/key-envelope.bin"

openssl pkeyutl -decrypt \
  -inkey "$TMP/buyer-private.pem" \
  -in "$TMP/key-envelope.bin" \
  -out "$TMP/aes.key" \
  -pkeyopt rsa_padding_mode:oaep \
  -pkeyopt rsa_oaep_md:sha256 \
  -pkeyopt rsa_mgf1_md:sha256

node - "$TMP/ciphertext.json" "$TMP/aes.key" "$TMP/plaintext.json" <<'NODE'
const crypto = require("crypto");
const fs = require("fs");
const envelope = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const key = fs.readFileSync(process.argv[3]);
const decipher = crypto.createDecipheriv("aes-256-gcm", key, Buffer.from(envelope.iv, "base64"));
decipher.setAuthTag(Buffer.from(envelope.tag, "base64"));
const plaintext = Buffer.concat([
  decipher.update(Buffer.from(envelope.ciphertext, "base64")),
  decipher.final(),
]);
const decoded = JSON.parse(plaintext.toString("utf8"));
if (decoded.payload?.name !== "DDTM V1 smoke dataset") {
  throw new Error("decrypted dataset does not match the listed payload");
}
fs.writeFileSync(process.argv[4], JSON.stringify(decoded, null, 2));
NODE

curl -fsS -X POST "$BASE_URL/v1/listings/$LISTING_ID/confirm" \
  -H "x-ddtm-api-key: $API_KEY" \
  -H "Idempotency-Key: smoke-confirm-001" \
  -H "content-type: application/json" \
  --data '{}' | tee "$TMP/confirm-response.json"

curl -fsS "$BASE_URL/v1/listings/$LISTING_ID" \
  -H "x-ddtm-api-key: $API_KEY" | tee "$TMP/final-listing.json"

node -e '
const x=require(process.argv[1]);
if(x.stateName!=="CONFIRMED") throw new Error(`unexpected final state: ${x.stateName}`);
console.log(`DDTM V1 smoke test passed: listing ${x.tid} reached ${x.stateName}`);
' "$TMP/final-listing.json"
