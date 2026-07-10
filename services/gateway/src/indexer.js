function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function createIndexer({ chain, db, pollMs, confirmations, logger = console }) {
  let stopped = false;
  let running = false;

  async function syncOnce() {
    if (running) return;
    running = true;
    try {
      const head = BigInt(await chain.provider.getBlockNumber());
      const safeHead = head - BigInt(Math.max(confirmations - 1, 0));
      if (safeHead < 0n) return;

      let next = await db.getCheckpoint(0n);
      while (!stopped && next <= safeHead) {
        const block = await chain.getBlock(Number(next));
        if (!block) break;

        const existing = await db.getBlock(next);
        if (existing && existing.block_hash !== block.hash) {
          logger.warn(`chain reorganization detected at block ${next}`);
          await db.rollbackFromBlock(next);
        }

        if (next > 0n) {
          const previous = await db.getBlock(next - 1n);
          if (previous && previous.block_hash !== block.parentHash) {
            const rewind = await findCommonAncestor(next - 1n);
            logger.warn(`parent mismatch at block ${next}; rewinding to ${rewind}`);
            await db.rollbackFromBlock(rewind);
            next = rewind;
            continue;
          }
        }

        await db.saveBlock({
          number: BigInt(block.number),
          hash: block.hash,
          parentHash: block.parentHash,
          timestamp: BigInt(block.timestamp),
        });

        const logs = await chain.getLogs(Number(next), Number(next));
        for (const log of logs) {
          let parsed;
          try {
            parsed = chain.parseLog(log);
          } catch {
            continue;
          }
          if (!parsed) continue;
          const payload = normalizeArgs(parsed.args);
          const listingId = payload.id ?? null;
          const tid = payload.tid ?? null;
          await db.saveEvent({
            blockNumber: BigInt(log.blockNumber),
            blockHash: log.blockHash,
            transactionHash: log.transactionHash,
            index: log.index,
            eventName: parsed.name,
            listingId,
            tid,
            payload,
          });
          if (listingId != null) {
            const local = await db.getListing(listingId);
            if (local) {
              const state = await chain.getState(listingId);
              await db.updateListing(listingId, { state });
            }
          }
        }

        next += 1n;
        await db.setCheckpoint(next);
      }
    } finally {
      running = false;
    }
  }

  async function findCommonAncestor(start) {
    let cursor = start;
    while (true) {
      const stored = await db.getBlock(cursor);
      const canonical = await chain.getBlock(Number(cursor));
      if (stored && canonical && stored.block_hash === canonical.hash) return cursor + 1n;
      if (cursor === 0n) return 0n;
      cursor -= 1n;
    }
  }

  async function start() {
    stopped = false;
    while (!stopped) {
      try {
        await syncOnce();
      } catch (error) {
        logger.error("indexer synchronization failed", error);
      }
      await sleep(pollMs);
    }
  }

  return Object.freeze({
    start,
    syncOnce,
    stop: () => {
      stopped = true;
    },
  });
}

function normalizeArgs(args) {
  const out = {};
  for (const [key, value] of Object.entries(args)) {
    if (/^\d+$/.test(key)) continue;
    if (typeof value === "bigint") out[key] = value.toString();
    else if (Array.isArray(value)) out[key] = value.map(normalizeValue);
    else out[key] = normalizeValue(value);
  }
  return out;
}

function normalizeValue(value) {
  if (typeof value === "bigint") return value.toString();
  if (value && typeof value === "object" && "toString" in value) return value.toString();
  return value;
}
