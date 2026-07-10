import { keccak256, toUtf8Bytes } from "ethers";
import {
  canonicalJson,
  decryptPrivateMaterial,
  digestToField,
  encryptPayload,
  encryptPrivateMaterial,
  randomScalar,
  recordsToBlocks,
  sealKeyForBuyer,
  sha256,
  sha256Hex,
} from "./crypto.js";

export function createOperations({ chain, db, storage, prover, config }) {
  async function withIdempotency(key, operation, request, work) {
    const requestHash = sha256Hex(Buffer.from(canonicalJson(request)));
    const claimed = await db.claimIdempotency({ key, operation, requestHash });
    if (!claimed.claimed) {
      if (claimed.record.status === "COMPLETED") return claimed.record.response;
      if (claimed.record.status === "PROCESSING") {
        const error = new Error("request is already being processed");
        error.statusCode = 409;
        throw error;
      }
      await db.query(
        `UPDATE api_idempotency SET status = 'PROCESSING', error_message = NULL, updated_at = now()
          WHERE idempotency_key = $1`,
        [key]
      );
    }

    try {
      const result = await work();
      await db.completeIdempotency(key, result, result.txHash ?? null);
      return result;
    } catch (error) {
      await db.failIdempotency(key, error.message ?? String(error));
      throw error;
    }
  }

  async function createListing(input, idempotencyKey) {
    return withIdempotency(idempotencyKey, "CREATE_LISTING", input, async () => {
      const asOfTime = BigInt(input.asOfTime ?? Math.floor(Date.now() / 1000));
      const blocks = recordsToBlocks(input.records, asOfTime);
      const material = {
        blocks,
        encRand: Array.from({ length: 16 }, () => randomScalar()),
        key: randomScalar(),
        rD: randomScalar(),
        rQ: randomScalar(),
        rK: randomScalar(),
        rEnc: randomScalar(),
      };
      const policy = {
        minPresent: String(input.minPresent ?? 1),
        maxValue: String(input.maxValue ?? "1000000000"),
        maxAge: String(input.maxAge ?? "86400"),
        asOfTime: asOfTime.toString(),
      };
      const witnessRequest = { ...material, ...policy, context: "0", buyerKey: "0" };
      const commitmentResult = await prover.commitments(witnessRequest);

      const plaintext = Buffer.from(
        canonicalJson({
          version: "ddtm-v1",
          records: input.records,
          payload: input.payload ?? null,
          createdAt: new Date().toISOString(),
        })
      );
      const encrypted = encryptPayload(plaintext, material.key);
      const objectSuffix = sha256(Buffer.from(idempotencyKey)).toString("hex");
      const objectKey = `ciphertexts/${objectSuffix}.json`;
      const stored = await storage.put(objectKey, encrypted.envelope, {
        contentType: "application/vnd.ddtm.ciphertext+json",
      });

      const contractTerms = input.contractTerms ?? {
        purpose: "research-data-trade",
        usage: "single-buyer",
      };
      const contractHash = sha256Hex(Buffer.from(canonicalJson(contractTerms)));
      const objectKeyHash = keccak256(toUtf8Bytes(objectKey));
      const price = BigInt(input.priceWei);
      if (price <= 0n) throw badRequest("priceWei must be a positive decimal integer");
      const nonce = BigInt(input.nonce ?? randomScalar());
      const terms = {
        cD: commitmentResult.commitments.cD,
        cQ: commitmentResult.commitments.cQ,
        cK: commitmentResult.commitments.cK,
        zkRoot: commitmentResult.commitments.zkRoot,
        objectDigest: stored.digest,
        objectKeyHash,
        contractHash,
        price,
        minPresent: BigInt(policy.minPresent),
        maxValue: BigInt(policy.maxValue),
        maxAge: BigInt(policy.maxAge),
        asOfTime,
        nonce,
      };
      const requestId = chainRequestId("CREATE_LISTING", idempotencyKey);

      try {
        const submitted = await chain.submit("seller", "list", [terms, requestId], {
          value: price / 10n || 1n,
        });
        const event = submitted.events.find((item) => item.name === "ListingCreated");
        if (!event) throw new Error("ListingCreated event was not emitted");
        const chainListingId = event.args.id.toString();
        const tid = event.args.tid;
        const secretMaterial = encryptPrivateMaterial(material, config.masterKey);
        await db.saveListing({
          chainListingId,
          tid,
          state: 0,
          sellerAddress: chain.roleAddress("seller"),
          objectKey,
          objectDigest: stored.digest,
          commitments: commitmentResult.commitments,
          policy,
          secretMaterial,
        });
        return {
          chainListingId,
          tid,
          state: "LISTED",
          object: publicObject(stored),
          commitments: commitmentResult.commitments,
          txHash: submitted.txHash,
        };
      } catch (error) {
        await storage.remove(objectKey).catch(() => undefined);
        throw error;
      }
    });
  }

  async function bid(input, idempotencyKey) {
    return withIdempotency(idempotencyKey, "BID", input, async () => {
      const id = requiredId(input.listingId);
      if (!input.buyerPublicKeyPem?.includes("BEGIN PUBLIC KEY")) {
        throw badRequest("buyerPublicKeyPem must be an RSA public key in PEM format");
      }
      const onChain = await chain.getListing(id);
      if (onChain.state !== 0) throw conflict(`listing is in ${onChain.stateName}`);
      const buyerKeyField = digestToField(sha256(Buffer.from(input.buyerPublicKeyPem)));
      const requestId = chainRequestId("BID", idempotencyKey);
      const submitted = await chain.submit(
        "buyer",
        "bid",
        [id, buyerKeyField, requestId],
        { value: BigInt(onChain.price) }
      );
      const row = await db.updateListing(id, {
        state: 1,
        buyerAddress: chain.roleAddress("buyer"),
        buyerPublicKey: input.buyerPublicKeyPem,
        buyerKeyField,
      });
      if (!row) throw new Error("local listing record was not found");
      return {
        listingId: String(id),
        tid: onChain.tid,
        state: "ESCROWED",
        buyerKeyField,
        context: await chain.getContext(id),
        txHash: submitted.txHash,
      };
    });
  }

  async function generateAndSubmitProofs(input, idempotencyKey) {
    return withIdempotency(idempotencyKey, "SUBMIT_PROOFS", input, async () => {
      const id = requiredId(input.listingId);
      const row = await db.getListing(id);
      if (!row) throw notFound("listing not found");
      const material = decryptPrivateMaterial(row.secret_material, config.masterKey);
      const base = {
        ...material,
        minPresent: String(row.policy.minPresent),
        maxValue: String(row.policy.maxValue),
        maxAge: String(row.policy.maxAge),
        asOfTime: String(row.policy.asOfTime),
      };
      const phaseTransactions = [];
      let onChain = await chain.getListing(id);
      const context = await chain.getContext(id);

      if (onChain.state === 1) {
        const quality = await prover.quality({ ...base, context, buyerKey: onChain.buyerKey });
        assertCommitments(row.commitments, quality.commitments);
        const submitted = await chain.submit("seller", "submitQualityProof", [
          id,
          quality.proof,
          quality.binding,
          chainRequestId("PI_Q", idempotencyKey),
        ]);
        phaseTransactions.push({ phase: "PI_Q", txHash: submitted.txHash });
        onChain = await chain.getListing(id);
      }

      if (onChain.state === 2) {
        const delivery = await prover.delivery({
          ...base,
          context,
          buyerKey: onChain.buyerKey,
          objectDigestField: digestToField(row.object_digest),
        });
        assertCommitments(row.commitments, delivery.commitments);
        const submitted = await chain.submit("seller", "submitDeliveryProof", [
          id,
          delivery.proof,
          delivery.binding,
          chainRequestId("PI_DELIVER", idempotencyKey),
        ]);
        phaseTransactions.push({ phase: "PI_DELIVER", txHash: submitted.txHash });
        onChain = await chain.getListing(id);
      }

      if (onChain.state === 3) {
        if (!row.buyer_public_key) throw new Error("buyer public key is missing");
        const sealed = sealKeyForBuyer(material.key, row.buyer_public_key);
        const envelopeKey = `key-envelopes/${row.tid.replace(/^0x/, "")}.bin`;
        const storedEnvelope = await storage.put(envelopeKey, sealed.envelope, {
          contentType: "application/octet-stream",
        });
        const keyProof = await prover.key({
          ...base,
          context,
          buyerKey: onChain.buyerKey,
          envelopeDigestField: digestToField(storedEnvelope.digest),
        });
        assertCommitments(row.commitments, keyProof.commitments);
        const submitted = await chain.submit("seller", "submitKeyProof", [
          id,
          keyProof.proof,
          keyProof.keyEnvelope,
          storedEnvelope.digest,
          keyProof.binding,
          chainRequestId("PI_KEY", idempotencyKey),
        ]);
        phaseTransactions.push({ phase: "PI_KEY", txHash: submitted.txHash });
        await db.updateListing(id, {
          state: 4,
          envelopeObjectKey: envelopeKey,
          envelopeDigest: storedEnvelope.digest,
        });
        onChain = await chain.getListing(id);
      }

      if (onChain.state < 4) {
        throw conflict(`proof orchestration stopped in ${onChain.stateName}`);
      }
      return {
        listingId: String(id),
        tid: onChain.tid,
        state: onChain.stateName,
        transactions: phaseTransactions,
        txHash: phaseTransactions.at(-1)?.txHash ?? null,
      };
    });
  }

  async function confirm(input, idempotencyKey) {
    return stateTransaction("CONFIRM", input, idempotencyKey, "buyer", "confirm", (id, requestId) => [id, requestId]);
  }

  async function openDispute(input, idempotencyKey) {
    return withIdempotency(idempotencyKey, "OPEN_DISPUTE", input, async () => {
      const id = requiredId(input.listingId);
      if (!input.evidence) throw badRequest("evidence is required");
      const evidence = Buffer.from(canonicalJson(input.evidence));
      const evidenceHash = sha256Hex(evidence);
      const objectKey = `evidence/${id}/${evidenceHash.replace(/^0x/, "")}.json`;
      await storage.put(objectKey, evidence, { contentType: "application/json" });
      const evidenceURIHash = keccak256(toUtf8Bytes(`minio://${storage.bucket}/${objectKey}`));
      const submitted = await chain.submit("buyer", "openDispute", [
        id,
        evidenceHash,
        evidenceURIHash,
        chainRequestId("OPEN_DISPUTE", idempotencyKey),
      ]);
      await db.updateListing(id, { state: 5 });
      return { listingId: String(id), state: "DISPUTED", evidenceHash, objectKey, txHash: submitted.txHash };
    });
  }

  async function resolveDispute(input, idempotencyKey) {
    return withIdempotency(idempotencyKey, "RESOLVE_DISPUTE", input, async () => {
      const id = requiredId(input.listingId);
      const decisionHash = sha256Hex(Buffer.from(canonicalJson(input.decision ?? {})));
      const submitted = await chain.submit("arbitrator", "resolveDispute", [
        id,
        Boolean(input.sellerWins),
        decisionHash,
        chainRequestId("RESOLVE_DISPUTE", idempotencyKey),
      ]);
      const onChain = await chain.getListing(id);
      await db.updateListing(id, { state: onChain.state });
      return { listingId: String(id), state: onChain.stateName, decisionHash, txHash: submitted.txHash };
    });
  }

  async function getListing(id) {
    const local = await db.getListing(requiredId(id));
    if (!local) throw notFound("listing not found");
    const onChain = await chain.getListing(id);
    return {
      ...onChain,
      objectKey: local.object_key,
      envelopeObjectKey: local.envelope_object_key,
      localState: Number(local.state),
      policy: local.policy,
    };
  }

  async function listListings() {
    const rows = await db.listListings();
    return rows.map((row) => ({
      listingId: row.chain_listing_id,
      tid: row.tid,
      state: Number(row.state),
      stateName: chain.stateNames[Number(row.state)] ?? "UNKNOWN",
      objectDigest: row.object_digest,
      createdAt: row.created_at,
    }));
  }

  async function downloadLinks(id) {
    const row = await db.getListing(requiredId(id));
    if (!row) throw notFound("listing not found");
    const result = {
      ciphertext: await storage.presignedGet(row.object_key, config.presignSeconds),
      expiresSeconds: config.presignSeconds,
    };
    if (row.envelope_object_key) {
      result.keyEnvelope = await storage.presignedGet(row.envelope_object_key, config.presignSeconds);
    }
    return result;
  }

  async function stateTransaction(operation, input, idempotencyKey, role, method, argsFactory) {
    return withIdempotency(idempotencyKey, operation, input, async () => {
      const id = requiredId(input.listingId);
      const submitted = await chain.submit(
        role,
        method,
        argsFactory(id, chainRequestId(operation, idempotencyKey))
      );
      const onChain = await chain.getListing(id);
      await db.updateListing(id, { state: onChain.state });
      return { listingId: String(id), state: onChain.stateName, txHash: submitted.txHash };
    });
  }

  return Object.freeze({
    createListing,
    bid,
    generateAndSubmitProofs,
    confirm,
    openDispute,
    resolveDispute,
    getListing,
    listListings,
    downloadLinks,
  });
}

function chainRequestId(operation, key) {
  return keccak256(toUtf8Bytes(`ddtm-v1:${operation}:${key}`));
}

function assertCommitments(expected, actual) {
  for (const key of ["cD", "cQ", "cK", "zkRoot"]) {
    if (String(expected[key]) !== String(actual[key])) {
      throw new Error(`prover commitment mismatch: ${key}`);
    }
  }
}

function requiredId(value) {
  if (!/^\d+$/.test(String(value ?? ""))) throw badRequest("listingId must be a non-negative integer");
  return BigInt(value);
}

function publicObject(stored) {
  return {
    bucket: stored.bucket,
    objectKey: stored.objectKey,
    digest: stored.digest,
    size: stored.size,
    etag: stored.etag,
  };
}

function errorWithStatus(message, statusCode) {
  const error = new Error(message);
  error.statusCode = statusCode;
  return error;
}

const badRequest = (message) => errorWithStatus(message, 400);
const notFound = (message) => errorWithStatus(message, 404);
const conflict = (message) => errorWithStatus(message, 409);
