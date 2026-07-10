#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${DDTM_BASE_URL:-http://127.0.0.1:8080}"
API_KEY="${GATEWAY_API_KEY:-ddtm-v1-local-api-key}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$TMP/buyer-private.pem" 2>/dev/null
openssl pkey -in "$TMP/buyer-private.pem" -pubout -out "$TMP/buyer-public.pem" 2>/dev/null

NOW="$(date +%s)"
cat >"$TMP/listing.json" <<JSON
{
  "records": [
    {"value":"41","timestamp":"$((NOW-30))","present":"1"},
    {"value":"42","timestamp":"$((NOW-20))","present":"1"},
    {"value":"43","timestamp":"$((NOW-10))","present":"1"}
  ],
  "payload": {"name":"DDTM V1 dispute dataset","purpose":"evidence-path validation"},
  "priceWei": "1000000000000000000",
  "minPresent": "3",
  "maxValue": "100",
  "maxAge": "300",
  "asOfTime": "$NOW",
  "contractTerms": {"purpose":"research","usage":"single-buyer","disputeTest":true}
}
JSON

create_listing() {
  curl -fsS -X POST "$BASE_URL/v1/listings" \
    -H "x-ddtm-api-key: $API_KEY" \
    -H "Idempotency-Key: dispute-listing-001" \
    -H "content-type: application/json" \
    --data-binary @"$TMP/listing.json"
}

create_listing | tee "$TMP/listing-response.json"
create_listing > "$TMP/listing-replay.json"
node -e '
const a=require(process.argv[1]); const b=require(process.argv[2]);
if(a.chainListingId!==b.chainListingId || a.tid!==b.tid) throw new Error("idempotent listing replay changed the result");
' "$TMP/listing-response.json" "$TMP/listing-replay.json"

LISTING_ID="$(node -e "const x=require(process.argv[1]);process.stdout.write(String(x.chainListingId))" "$TMP/listing-response.json")"
node -e 'const fs=require("fs"); fs.writeFileSync(process.argv[2], JSON.stringify({buyerPublicKeyPem:fs.readFileSync(process.argv[1],"utf8")}))' \
  "$TMP/buyer-public.pem" "$TMP/bid.json"

curl -fsS -X POST "$BASE_URL/v1/listings/$LISTING_ID/bids" \
  -H "x-ddtm-api-key: $API_KEY" \
  -H "Idempotency-Key: dispute-bid-001" \
  -H "content-type: application/json" \
  --data-binary @"$TMP/bid.json" > "$TMP/bid-response.json"

curl -fsS -X POST "$BASE_URL/v1/listings/$LISTING_ID/proofs" \
  -H "x-ddtm-api-key: $API_KEY" \
  -H "Idempotency-Key: dispute-proofs-001" \
  -H "content-type: application/json" \
  --data '{}' > "$TMP/proofs-response.json"

cat >"$TMP/dispute.json" <<JSON
{
  "evidence": {
    "type":"SEMANTIC_QUALITY_MISMATCH",
    "details":"The delivered payload does not satisfy the negotiated external business label.",
    "sampleReference":"sample-001"
  }
}
JSON

curl -fsS -X POST "$BASE_URL/v1/listings/$LISTING_ID/disputes" \
  -H "x-ddtm-api-key: $API_KEY" \
  -H "Idempotency-Key: dispute-open-001" \
  -H "content-type: application/json" \
  --data-binary @"$TMP/dispute.json" | tee "$TMP/dispute-response.json"

cat >"$TMP/decision.json" <<JSON
{
  "sellerWins": false,
  "decision": {
    "reason":"The evidence bundle supports the buyer claim in this V1 arbitration test.",
    "evidenceReviewed":true
  }
}
JSON

curl -fsS -X POST "$BASE_URL/v1/listings/$LISTING_ID/disputes/resolve" \
  -H "x-ddtm-api-key: $API_KEY" \
  -H "Idempotency-Key: dispute-resolve-001" \
  -H "content-type: application/json" \
  --data-binary @"$TMP/decision.json" | tee "$TMP/decision-response.json"

curl -fsS "$BASE_URL/v1/listings/$LISTING_ID" \
  -H "x-ddtm-api-key: $API_KEY" | tee "$TMP/final-listing.json"

node -e '
const x=require(process.argv[1]);
if(x.stateName!=="REFUNDED") throw new Error(`unexpected final state: ${x.stateName}`);
console.log(`DDTM V1 dispute smoke passed: listing ${x.tid} reached ${x.stateName}`);
' "$TMP/final-listing.json"
