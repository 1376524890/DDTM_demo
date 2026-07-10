import { fileURLToPath } from "node:url";
import express from "express";
import { requireApiKey, requireIdempotency } from "./auth.js";
import { createChain } from "./chain.js";
import { loadConfig } from "./config.js";
import { createDatabase } from "./db.js";
import { createIndexer } from "./indexer.js";
import { createOperations } from "./operations.js";
import { createProver } from "./prover.js";
import { createStorage } from "./storage.js";

export async function createApplication(overrides = {}) {
  const config = overrides.config ?? loadConfig();
  const db = overrides.db ?? createDatabase(config.databaseUrl);
  const storage = overrides.storage ?? createStorage(config.minio);
  const prover = overrides.prover ?? createProver({
    baseUrl: config.proverUrl,
    sharedSecret: config.proverSharedSecret,
    timeoutMs: config.requestTimeoutMs,
  });
  const chain = overrides.chain ?? (await createChain(config));
  const operations = overrides.operations ?? createOperations({ chain, db, storage, prover, config });
  const indexer = overrides.indexer ?? createIndexer({
    chain,
    db,
    pollMs: config.indexerPollMs,
    confirmations: config.confirmations,
  });

  await storage.ensureBucket();
  await db.query("SELECT 1");

  const app = express();
  app.disable("x-powered-by");
  app.use(express.json({ limit: "2mb", strict: true }));

  app.get("/health", async (_req, res, next) => {
    try {
      await db.query("SELECT 1");
      res.json({
        status: "ok",
        version: "ddtm-v1",
        chainId: chain.chainId.toString(),
        contract: chain.address,
        storage: `minio://${storage.bucket}`,
      });
    } catch (error) {
      next(error);
    }
  });

  const api = express.Router();
  api.use(requireApiKey(config.apiKey));

  api.get("/listings", asyncHandler(async (_req, res) => {
    res.json({ items: await operations.listListings() });
  }));

  api.get("/listings/:id", asyncHandler(async (req, res) => {
    res.json(await operations.getListing(req.params.id));
  }));

  api.get("/listings/:id/downloads", asyncHandler(async (req, res) => {
    res.json(await operations.downloadLinks(req.params.id));
  }));

  api.get("/listings/:id/artifacts/:kind", asyncHandler(async (req, res) => {
    const row = await db.getListing(req.params.id);
    if (!row) {
      res.status(404).json({ error: "listing_not_found" });
      return;
    }
    const isCiphertext = req.params.kind === "ciphertext";
    const isEnvelope = req.params.kind === "key-envelope";
    if (!isCiphertext && !isEnvelope) {
      res.status(404).json({ error: "artifact_not_found" });
      return;
    }
    const objectKey = isCiphertext ? row.object_key : row.envelope_object_key;
    const digest = isCiphertext ? row.object_digest : row.envelope_digest;
    if (!objectKey) {
      res.status(409).json({ error: "artifact_not_available" });
      return;
    }
    const object = await storage.get(objectKey, digest);
    res.type(isCiphertext ? "application/vnd.ddtm.ciphertext+json" : "application/octet-stream");
    res.set("x-ddtm-sha256", object.digest);
    res.send(object.body);
  }));

  api.post("/listings", requireIdempotency, asyncHandler(async (req, res) => {
    const result = await operations.createListing(req.body, req.idempotencyKey);
    res.status(201).json(result);
  }));

  api.post("/listings/:id/bids", requireIdempotency, asyncHandler(async (req, res) => {
    res.json(await operations.bid({ ...req.body, listingId: req.params.id }, req.idempotencyKey));
  }));

  api.post("/listings/:id/proofs", requireIdempotency, asyncHandler(async (req, res) => {
    res.json(
      await operations.generateAndSubmitProofs(
        { ...req.body, listingId: req.params.id },
        req.idempotencyKey
      )
    );
  }));

  api.post("/listings/:id/confirm", requireIdempotency, asyncHandler(async (req, res) => {
    res.json(await operations.confirm({ listingId: req.params.id }, req.idempotencyKey));
  }));

  api.post("/listings/:id/disputes", requireIdempotency, asyncHandler(async (req, res) => {
    res.json(
      await operations.openDispute(
        { ...req.body, listingId: req.params.id },
        req.idempotencyKey
      )
    );
  }));

  api.post("/listings/:id/disputes/resolve", requireIdempotency, asyncHandler(async (req, res) => {
    res.json(
      await operations.resolveDispute(
        { ...req.body, listingId: req.params.id },
        req.idempotencyKey
      )
    );
  }));

  app.use("/v1", api);
  app.use((_req, res) => res.status(404).json({ error: "not_found" }));
  app.use((error, _req, res, _next) => {
    console.error(error);
    const status = Number(error.statusCode) || 500;
    res.status(status).json({
      error: status >= 500 ? "internal_error" : "request_error",
      message: error.message,
    });
  });

  return { app, config, db, storage, chain, operations, indexer };
}

function asyncHandler(handler) {
  return (req, res, next) => Promise.resolve(handler(req, res, next)).catch(next);
}

async function main() {
  const runtime = await createApplication();
  const server = runtime.app.listen(runtime.config.port, () => {
    console.log(`DDTM V1 gateway listening on :${runtime.config.port}`);
  });
  runtime.indexer.start().catch((error) => console.error("indexer stopped", error));

  const shutdown = async (signal) => {
    console.log(`received ${signal}; shutting down`);
    runtime.indexer.stop();
    server.close(async () => {
      await runtime.db.close();
      process.exit(0);
    });
  };
  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
