import assert from "node:assert/strict";
import { generateKeyPairSync, privateDecrypt, constants as cryptoConstants } from "node:crypto";
import test from "node:test";
import {
  canonicalJson,
  decryptPayload,
  digestToField,
  encryptPayload,
  recordsToBlocks,
  sealKeyForBuyer,
  sha256Hex,
  SNARK_SCALAR_FIELD,
} from "../src/crypto.js";

test("canonicalJson orders object keys deterministically", () => {
  assert.equal(canonicalJson({ z: 1, a: { d: 2, b: 1 } }), '{"a":{"b":1,"d":2},"z":1}');
});

test("AES-256-GCM ciphertext decrypts and detects tampering", () => {
  const plaintext = Buffer.from("DDTM research payload");
  const encrypted = encryptPayload(plaintext, "123456789");
  assert.deepEqual(decryptPayload(encrypted.envelope, "123456789"), plaintext);
  assert.equal(encrypted.digest, sha256Hex(encrypted.envelope));

  const tampered = Buffer.from(encrypted.envelope);
  tampered[tampered.length - 2] ^= 1;
  assert.throws(() => decryptPayload(tampered, "123456789"));
});

test("RSA-OAEP key envelope contains the derived AES key", () => {
  const { publicKey, privateKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
  const sealed = sealKeyForBuyer("999", publicKey.export({ type: "spki", format: "pem" }));
  const opened = privateDecrypt(
    {
      key: privateKey,
      oaepHash: "sha256",
      padding: cryptoConstants.RSA_PKCS1_OAEP_PADDING,
    },
    sealed.envelope
  );
  assert.equal(opened.length, 32);
  assert.equal(sealed.digest, sha256Hex(sealed.envelope));
});

test("record encoding produces the fixed 16-field circuit layout", () => {
  const blocks = recordsToBlocks([{ value: 7, timestamp: 100, present: 1 }], 120);
  assert.equal(blocks.length, 16);
  assert.deepEqual(blocks.slice(0, 4), ["7", "100", "1", "0"]);
  assert.deepEqual(blocks.slice(4, 8), ["0", "120", "0", "0"]);
  assert.throws(() => recordsToBlocks([{ value: 1, timestamp: 100, present: 0 }], 120));
});

test("digestToField always returns a valid BN254 scalar", () => {
  const value = BigInt(digestToField(sha256Hex(Buffer.from("field"))));
  assert.ok(value >= 0n && value < SNARK_SCALAR_FIELD);
});
