import { createHmac } from "node:crypto";
import { canonicalJson } from "./crypto.js";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function createProver({ baseUrl, sharedSecret, timeoutMs }) {
  async function prove(type, payload, attempts = 3) {
    const body = canonicalJson(payload);
    let lastError;

    for (let attempt = 0; attempt < attempts; attempt += 1) {
      const timestamp = Math.floor(Date.now() / 1000).toString();
      const signature = createHmac("sha256", sharedSecret)
        .update(`${timestamp}.${body}`)
        .digest("hex");
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(`${baseUrl}/v1/proofs/${type}`, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "x-ddtm-timestamp": timestamp,
            "x-ddtm-signature": signature,
          },
          body,
          signal: controller.signal,
        });
        const text = await response.text();
        if (!response.ok) {
          const error = new Error(`prover ${type} failed (${response.status}): ${text}`);
          error.retryable = response.status >= 500 || response.status === 429;
          throw error;
        }
        const decoded = JSON.parse(text);
        validateProofResponse(type, decoded);
        return decoded;
      } catch (error) {
        lastError = error;
        const retryable = error.name === "AbortError" || error.retryable === true;
        if (!retryable || attempt === attempts - 1) break;
        await sleep(250 * 2 ** attempt);
      } finally {
        clearTimeout(timer);
      }
    }
    throw lastError;
  }

  return Object.freeze({
    commitments: (payload) => prove("commitments", payload),
    quality: (payload) => prove("quality", payload),
    key: (payload) => prove("key", payload),
    delivery: (payload) => prove("delivery", payload),
  });
}

function validateProofResponse(type, value) {
  if (!value || value.type !== type || value.curve !== "BN254" || value.scheme !== "Groth16") {
    throw new Error("prover returned an incompatible response");
  }
  for (const key of ["cD", "cQ", "cK", "zkRoot"]) {
    if (!/^\d+$/.test(value.commitments?.[key] ?? "")) {
      throw new Error(`prover response is missing decimal commitment ${key}`);
    }
  }
  if (type !== "commitments") {
    if (!/^0x[0-9a-f]{512}$/i.test(value.proof ?? "")) {
      throw new Error("prover response has an invalid Groth16 proof encoding");
    }
    if (!Array.isArray(value.publicInputs) || !value.publicInputs.every((item) => /^\d+$/.test(item))) {
      throw new Error("prover response has invalid public inputs");
    }
    if (!/^\d+$/.test(value.binding ?? "")) {
      throw new Error("prover response has an invalid binding");
    }
  }
}
