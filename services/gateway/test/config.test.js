import assert from "node:assert/strict";
import test from "node:test";
import { loadConfig } from "../src/config.js";

const valid = {
  GATEWAY_API_KEY: "api-key",
  GATEWAY_MASTER_KEY: "master-key",
  DATABASE_URL: "postgresql://localhost/ddtm",
  PROVER_SHARED_SECRET: "prover-secret",
  MINIO_ROOT_USER: "minio-user",
  MINIO_ROOT_PASSWORD: "minio-password",
};

test("loadConfig supplies deterministic local defaults", () => {
  const config = loadConfig(valid);
  assert.equal(config.rpcUrl, "http://hardhat:8545");
  assert.equal(config.minio.bucket, "ddtm-v1");
  assert.match(config.localMnemonic, /^test test/);
});

test("loadConfig rejects missing secrets", () => {
  assert.throws(() => loadConfig({}), /GATEWAY_API_KEY/);
});
