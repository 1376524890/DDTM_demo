import assert from "node:assert/strict";
import test from "node:test";
import { requireApiKey, requireIdempotency } from "../src/auth.js";

function response() {
  return {
    statusCode: 200,
    body: null,
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(value) {
      this.body = value;
      return this;
    },
  };
}

test("API key middleware accepts the configured key", () => {
  const req = { get: (name) => (name === "x-ddtm-api-key" ? "secret" : undefined) };
  const res = response();
  let called = false;
  requireApiKey("secret")(req, res, () => {
    called = true;
  });
  assert.equal(called, true);
  assert.equal(res.statusCode, 200);
});

test("API key middleware rejects an invalid key", () => {
  const req = { get: () => "wrong" };
  const res = response();
  requireApiKey("secret")(req, res, () => assert.fail("next must not run"));
  assert.equal(res.statusCode, 401);
});

test("idempotency middleware validates and stores the key", () => {
  const req = { get: () => "listing:request-001" };
  const res = response();
  let called = false;
  requireIdempotency(req, res, () => {
    called = true;
  });
  assert.equal(called, true);
  assert.equal(req.idempotencyKey, "listing:request-001");
});

test("idempotency middleware rejects malformed values", () => {
  const req = { get: () => "bad key with spaces" };
  const res = response();
  requireIdempotency(req, res, () => assert.fail("next must not run"));
  assert.equal(res.statusCode, 400);
});
