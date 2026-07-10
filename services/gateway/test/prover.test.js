import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import http from "node:http";
import test from "node:test";
import { createProver } from "../src/prover.js";

const commitments = { cD: "1", cQ: "2", cK: "3", zkRoot: "4" };

test("prover client signs the exact canonical request body", async (t) => {
  const secret = "shared-test-secret";
  const server = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const body = Buffer.concat(chunks).toString("utf8");
    const timestamp = req.headers["x-ddtm-timestamp"];
    const expected = createHmac("sha256", secret).update(`${timestamp}.${body}`).digest("hex");
    assert.equal(req.headers["x-ddtm-signature"], expected);
    res.setHeader("content-type", "application/json");
    res.end(
      JSON.stringify({
        type: "quality",
        curve: "BN254",
        scheme: "Groth16",
        commitments,
        proof: `0x${"00".repeat(256)}`,
        publicInputs: ["1", "2"],
        binding: "5",
      })
    );
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => server.close());
  const address = server.address();
  const prover = createProver({
    baseUrl: `http://127.0.0.1:${address.port}`,
    sharedSecret: secret,
    timeoutMs: 5000,
  });
  const result = await prover.quality({ z: 1, a: 2 });
  assert.equal(result.binding, "5");
});
