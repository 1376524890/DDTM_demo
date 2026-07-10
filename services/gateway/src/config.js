export function loadConfig(env = process.env) {
  const required = (name) => {
    const value = env[name];
    if (!value) throw new Error(`Missing required environment variable: ${name}`);
    return value;
  };

  const integer = (name, fallback) => {
    const raw = env[name] ?? String(fallback);
    const value = Number.parseInt(raw, 10);
    if (!Number.isFinite(value) || value <= 0) throw new Error(`Invalid positive integer: ${name}`);
    return value;
  };

  return Object.freeze({
    port: integer("GATEWAY_PORT", 8080),
    apiKey: required("GATEWAY_API_KEY"),
    masterKey: required("GATEWAY_MASTER_KEY"),
    databaseUrl: required("DATABASE_URL"),
    rpcUrl: env.RPC_URL ?? "http://hardhat:8545",
    deploymentFile: env.DEPLOYMENT_FILE ?? "/app/deployments/v1.json",
    contractAddress: env.DDTM_CONTRACT_ADDRESS ?? "",
    localMnemonic:
      env.LOCAL_MNEMONIC ?? "test test test test test test test test test test test junk",
    sellerPrivateKey: env.SELLER_PRIVATE_KEY ?? "",
    buyerPrivateKey: env.BUYER_PRIVATE_KEY ?? "",
    arbitratorPrivateKey: env.ARBITRATOR_PRIVATE_KEY ?? "",
    proverUrl: env.PROVER_URL ?? "http://prover:8081",
    proverSharedSecret: required("PROVER_SHARED_SECRET"),
    minio: Object.freeze({
      endPoint: env.MINIO_ENDPOINT ?? "minio",
      port: integer("MINIO_PORT", 9000),
      useSSL: (env.MINIO_USE_SSL ?? "false").toLowerCase() === "true",
      accessKey: required("MINIO_ROOT_USER"),
      secretKey: required("MINIO_ROOT_PASSWORD"),
      bucket: env.MINIO_BUCKET ?? "ddtm-v1",
    }),
    confirmations: integer("CHAIN_CONFIRMATIONS", 1),
    requestTimeoutMs: integer("REQUEST_TIMEOUT_MS", 120000),
    indexerPollMs: integer("INDEXER_POLL_MS", 1000),
    presignSeconds: integer("PRESIGN_SECONDS", 300),
  });
}
