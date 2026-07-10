import assert from "node:assert/strict";
import test from "node:test";
import { DDTM_VERSION } from "../src/version.js";

test("prototype version is stable", () => {
  assert.equal(DDTM_VERSION, "ddtm-v1");
});
