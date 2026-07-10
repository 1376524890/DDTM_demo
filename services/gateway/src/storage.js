import { Client } from "minio";
import { sha256Hex } from "./crypto.js";

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isNotFound(error) {
  return ["NoSuchKey", "NotFound", "NoSuchObject"].includes(error?.code);
}

async function retry(work, { attempts = 5, baseMs = 200, shouldRetry = () => true } = {}) {
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await work();
    } catch (error) {
      lastError = error;
      if (!shouldRetry(error) || attempt === attempts - 1) break;
      await delay(baseMs * 2 ** attempt);
    }
  }
  throw lastError;
}

export function createStorage(config) {
  const client = new Client({
    endPoint: config.endPoint,
    port: config.port,
    useSSL: config.useSSL,
    accessKey: config.accessKey,
    secretKey: config.secretKey,
  });
  const bucket = config.bucket;

  async function ensureBucket() {
    await retry(async () => {
      const exists = await client.bucketExists(bucket);
      if (!exists) await client.makeBucket(bucket, "us-east-1");
    });
  }

  async function put(objectKey, data, metadata = {}) {
    const body = Buffer.isBuffer(data) ? data : Buffer.from(data);
    const digest = sha256Hex(body);

    const existing = await existingObject(objectKey);
    if (existing) {
      if (existing.digest.toLowerCase() !== digest.toLowerCase()) {
        const error = new Error(`immutable MinIO object already exists with different bytes: ${objectKey}`);
        error.code = "ImmutableObjectConflict";
        throw error;
      }
      return {
        bucket,
        objectKey,
        digest,
        size: existing.body.length,
        etag: existing.stat.etag,
        versionId: existing.stat.versionId ?? null,
        reused: true,
      };
    }

    const normalized = {
      "content-type": metadata.contentType ?? "application/octet-stream",
      "x-amz-meta-ddtm-sha256": digest.replace(/^0x/, ""),
      ...metadata.extra,
    };
    await retry(() => client.putObject(bucket, objectKey, body, body.length, normalized));
    const statResult = await retry(() => client.statObject(bucket, objectKey));
    const storedDigest =
      statResult.metaData?.["ddtm-sha256"] ?? statResult.metaData?.["x-amz-meta-ddtm-sha256"];
    if (storedDigest && storedDigest.toLowerCase() !== digest.replace(/^0x/, "").toLowerCase()) {
      throw new Error("MinIO metadata digest mismatch after upload");
    }
    return {
      bucket,
      objectKey,
      digest,
      size: body.length,
      etag: statResult.etag,
      versionId: statResult.versionId ?? null,
      reused: false,
    };
  }

  async function existingObject(objectKey) {
    let statResult;
    try {
      statResult = await retry(() => client.statObject(bucket, objectKey), {
        shouldRetry: (error) => !isNotFound(error),
      });
    } catch (error) {
      if (isNotFound(error)) return null;
      throw error;
    }
    const stream = await retry(() => client.getObject(bucket, objectKey));
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    const body = Buffer.concat(chunks);
    return { stat: statResult, body, digest: sha256Hex(body) };
  }

  async function get(objectKey, expectedDigest = null) {
    const stream = await retry(() => client.getObject(bucket, objectKey));
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    const body = Buffer.concat(chunks);
    const digest = sha256Hex(body);
    if (expectedDigest && digest.toLowerCase() !== expectedDigest.toLowerCase()) {
      throw new Error(`MinIO object digest mismatch for ${objectKey}`);
    }
    return { body, digest };
  }

  async function stat(objectKey) {
    const result = await retry(() => client.statObject(bucket, objectKey));
    return {
      size: result.size,
      etag: result.etag,
      lastModified: result.lastModified,
      versionId: result.versionId ?? null,
      metadata: result.metaData ?? {},
    };
  }

  async function remove(objectKey) {
    await retry(() => client.removeObject(bucket, objectKey));
  }

  async function presignedGet(objectKey, expiresSeconds) {
    return retry(() => client.presignedGetObject(bucket, objectKey, expiresSeconds));
  }

  return Object.freeze({
    client,
    bucket,
    ensureBucket,
    put,
    get,
    stat,
    remove,
    presignedGet,
  });
}
