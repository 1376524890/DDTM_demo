import {
  createCipheriv,
  createDecipheriv,
  createHash,
  publicEncrypt,
  randomBytes,
  constants as cryptoConstants,
} from "node:crypto";

export const SNARK_SCALAR_FIELD = BigInt(
  "21888242871839275222246405745257275088548364400416034343698204186575808495617"
);

export function canonicalJson(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  return `{${Object.keys(value)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
    .join(",")}}`;
}

export function sha256(data) {
  return createHash("sha256").update(data).digest();
}

export function sha256Hex(data) {
  return `0x${sha256(data).toString("hex")}`;
}

export function digestToField(digest) {
  const buffer = Buffer.isBuffer(digest)
    ? digest
    : Buffer.from(String(digest).replace(/^0x/, ""), "hex");
  return (BigInt(`0x${buffer.toString("hex")}`) % SNARK_SCALAR_FIELD).toString();
}

export function randomScalar() {
  while (true) {
    const candidate = BigInt(`0x${randomBytes(32).toString("hex")}`);
    if (candidate > 0n && candidate < SNARK_SCALAR_FIELD) return candidate.toString();
  }
}

export function scalarToBytes(value) {
  const hex = BigInt(value).toString(16).padStart(64, "0");
  return Buffer.from(hex, "hex");
}

export function deriveAesKey(keyScalar) {
  return sha256(scalarToBytes(keyScalar));
}

export function recordsToBlocks(records, asOfTime) {
  if (!Array.isArray(records) || records.length > 4) {
    throw new Error("records must be an array with at most four entries");
  }
  const blocks = [];
  for (let i = 0; i < 4; i += 1) {
    const record = records[i] ?? { value: "0", timestamp: String(asOfTime), present: "0" };
    const value = BigInt(record.value ?? 0);
    const timestamp = BigInt(record.timestamp ?? asOfTime);
    const present = BigInt(record.present ?? 1);
    if (value < 0n || timestamp < 0n || (present !== 0n && present !== 1n)) {
      throw new Error(`invalid record at index ${i}`);
    }
    if (present === 0n && value !== 0n) {
      throw new Error(`missing record ${i} must have value 0`);
    }
    blocks.push(value.toString(), timestamp.toString(), present.toString(), "0");
  }
  return blocks;
}

export function encryptPayload(plaintext, keyScalar) {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", deriveAesKey(keyScalar), iv);
  const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const tag = cipher.getAuthTag();
  const envelope = Buffer.from(
    JSON.stringify({
      version: 1,
      algorithm: "AES-256-GCM",
      iv: iv.toString("base64"),
      tag: tag.toString("base64"),
      ciphertext: ciphertext.toString("base64"),
    })
  );
  return { envelope, digest: sha256Hex(envelope) };
}

export function decryptPayload(envelope, keyScalar) {
  const parsed = JSON.parse(Buffer.from(envelope).toString("utf8"));
  if (parsed.version !== 1 || parsed.algorithm !== "AES-256-GCM") {
    throw new Error("unsupported ciphertext envelope");
  }
  const decipher = createDecipheriv(
    "aes-256-gcm",
    deriveAesKey(keyScalar),
    Buffer.from(parsed.iv, "base64")
  );
  decipher.setAuthTag(Buffer.from(parsed.tag, "base64"));
  return Buffer.concat([
    decipher.update(Buffer.from(parsed.ciphertext, "base64")),
    decipher.final(),
  ]);
}

export function sealKeyForBuyer(keyScalar, buyerPublicKeyPem) {
  const envelope = publicEncrypt(
    {
      key: buyerPublicKeyPem,
      oaepHash: "sha256",
      padding: cryptoConstants.RSA_PKCS1_OAEP_PADDING,
    },
    deriveAesKey(keyScalar)
  );
  return { envelope, digest: sha256Hex(envelope) };
}

export function encryptPrivateMaterial(material, masterKey) {
  const iv = randomBytes(12);
  const key = sha256(Buffer.from(masterKey, "utf8"));
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const ciphertext = Buffer.concat([
    cipher.update(Buffer.from(canonicalJson(material))),
    cipher.final(),
  ]);
  return {
    ciphertext: ciphertext.toString("base64"),
    iv: iv.toString("base64"),
    tag: cipher.getAuthTag().toString("base64"),
  };
}

export function decryptPrivateMaterial(record, masterKey) {
  const key = sha256(Buffer.from(masterKey, "utf8"));
  const decipher = createDecipheriv("aes-256-gcm", key, Buffer.from(record.iv, "base64"));
  decipher.setAuthTag(Buffer.from(record.tag, "base64"));
  const plaintext = Buffer.concat([
    decipher.update(Buffer.from(record.ciphertext, "base64")),
    decipher.final(),
  ]);
  return JSON.parse(plaintext.toString("utf8"));
}
