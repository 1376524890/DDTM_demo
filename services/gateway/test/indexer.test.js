import assert from "node:assert/strict";
import test from "node:test";
import { createIndexer } from "../src/indexer.js";

function block(number, hash, parentHash) {
  return { number, hash, parentHash, timestamp: 1_700_000_000 + number };
}

test("indexer rewinds to the common ancestor after a chain reorganization", async () => {
  let head = 1;
  const canonical = new Map([
    [0, block(0, "0x00", "0x00")],
    [1, block(1, "0x01a", "0x00")],
  ]);
  const storedBlocks = new Map();
  const rollbackCalls = [];
  let checkpoint = 0n;

  const chain = {
    provider: { getBlockNumber: async () => head },
    getBlock: async (number) => canonical.get(Number(number)) ?? null,
    getLogs: async () => [],
    parseLog: () => null,
    getState: async () => 0,
  };
  const db = {
    getCheckpoint: async () => checkpoint,
    setCheckpoint: async (value) => {
      checkpoint = BigInt(value);
    },
    getBlock: async (number) => storedBlocks.get(Number(number)) ?? null,
    saveBlock: async (value) => {
      storedBlocks.set(Number(value.number), {
        block_number: String(value.number),
        block_hash: value.hash,
        parent_hash: value.parentHash,
      });
    },
    rollbackFromBlock: async (number) => {
      const start = Number(number);
      rollbackCalls.push(start);
      for (const key of [...storedBlocks.keys()]) {
        if (key >= start) storedBlocks.delete(key);
      }
      checkpoint = BigInt(start);
    },
    saveEvent: async () => undefined,
    getListing: async () => null,
    updateListing: async () => undefined,
  };

  const indexer = createIndexer({
    chain,
    db,
    pollMs: 1,
    confirmations: 1,
    logger: { warn() {}, error() {} },
  });

  await indexer.syncOnce();
  assert.equal(checkpoint, 2n);
  assert.equal(storedBlocks.get(1).block_hash, "0x01a");

  canonical.set(1, block(1, "0x01b", "0x00"));
  canonical.set(2, block(2, "0x02b", "0x01b"));
  head = 2;

  await indexer.syncOnce();
  assert.deepEqual(rollbackCalls, [1]);
  assert.equal(checkpoint, 3n);
  assert.equal(storedBlocks.get(1).block_hash, "0x01b");
  assert.equal(storedBlocks.get(2).parent_hash, "0x01b");
});
