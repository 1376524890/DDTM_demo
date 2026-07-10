import { timingSafeEqual } from "node:crypto";

function equalSecret(left, right) {
  const a = Buffer.from(String(left));
  const b = Buffer.from(String(right));
  return a.length === b.length && timingSafeEqual(a, b);
}

export function requireApiKey(expected) {
  return (req, res, next) => {
    const bearer = req.get("authorization")?.replace(/^Bearer\s+/i, "");
    const provided = req.get("x-ddtm-api-key") ?? bearer ?? "";
    if (!equalSecret(provided, expected)) {
      res.status(401).json({ error: "unauthorized" });
      return;
    }
    next();
  };
}

export function requireIdempotency(req, res, next) {
  const key = req.get("idempotency-key");
  if (!key || key.length < 8 || key.length > 128) {
    res.status(400).json({ error: "Idempotency-Key must contain 8 to 128 characters" });
    return;
  }
  if (!/^[A-Za-z0-9._:-]+$/.test(key)) {
    res.status(400).json({ error: "Idempotency-Key contains unsupported characters" });
    return;
  }
  req.idempotencyKey = key;
  next();
}
