import pg from "pg";

const { Pool } = pg;

export function createDatabase(connectionString) {
  const pool = new Pool({
    connectionString,
    max: 10,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 10_000,
  });

  async function query(text, params = []) {
    return pool.query(text, params);
  }

  async function transaction(work) {
    const client = await pool.connect();
    try {
      await client.query("BEGIN");
      const result = await work(client);
      await client.query("COMMIT");
      return result;
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }

  async function claimIdempotency({ key, operation, requestHash }) {
    return transaction(async (client) => {
      const inserted = await client.query(
        `INSERT INTO api_idempotency (idempotency_key, operation, request_hash, status)
         VALUES ($1, $2, $3, 'PROCESSING')
         ON CONFLICT (idempotency_key) DO NOTHING
         RETURNING *`,
        [key, operation, requestHash]
      );
      if (inserted.rowCount === 1) {
        return { claimed: true, record: inserted.rows[0] };
      }

      const existing = await client.query(
        `SELECT * FROM api_idempotency WHERE idempotency_key = $1 FOR UPDATE`,
        [key]
      );
      const record = existing.rows[0];
      if (!record) throw new Error("idempotency record disappeared");
      if (record.operation !== operation || record.request_hash !== requestHash) {
        const error = new Error("Idempotency-Key was already used with a different request");
        error.statusCode = 409;
        throw error;
      }
      return { claimed: false, record };
    });
  }

  async function completeIdempotency(key, response, txHash = null) {
    await query(
      `UPDATE api_idempotency
          SET status = 'COMPLETED', response = $2::jsonb, tx_hash = $3,
              error_message = NULL, updated_at = now()
        WHERE idempotency_key = $1`,
      [key, JSON.stringify(response), txHash]
    );
  }

  async function failIdempotency(key, errorMessage) {
    await query(
      `UPDATE api_idempotency
          SET status = 'FAILED', error_message = $2, updated_at = now()
        WHERE idempotency_key = $1`,
      [key, String(errorMessage).slice(0, 4000)]
    );
  }

  async function saveListing(record) {
    const result = await query(
      `INSERT INTO listings (
          chain_listing_id, tid, state, seller_address, buyer_address,
          object_key, object_digest, envelope_object_key, envelope_digest,
          commitments, policy, buyer_public_key, buyer_key_field, secret_material
       ) VALUES (
          $1, $2, $3, $4, $5,
          $6, $7, $8, $9,
          $10::jsonb, $11::jsonb, $12, $13, $14::jsonb
       )
       ON CONFLICT (chain_listing_id) DO UPDATE SET
          tid = EXCLUDED.tid,
          state = EXCLUDED.state,
          seller_address = EXCLUDED.seller_address,
          buyer_address = COALESCE(EXCLUDED.buyer_address, listings.buyer_address),
          object_key = EXCLUDED.object_key,
          object_digest = EXCLUDED.object_digest,
          envelope_object_key = COALESCE(EXCLUDED.envelope_object_key, listings.envelope_object_key),
          envelope_digest = COALESCE(EXCLUDED.envelope_digest, listings.envelope_digest),
          commitments = EXCLUDED.commitments,
          policy = EXCLUDED.policy,
          buyer_public_key = COALESCE(EXCLUDED.buyer_public_key, listings.buyer_public_key),
          buyer_key_field = COALESCE(EXCLUDED.buyer_key_field, listings.buyer_key_field),
          secret_material = EXCLUDED.secret_material,
          updated_at = now()
       RETURNING *`,
      [
        record.chainListingId,
        record.tid,
        record.state,
        record.sellerAddress,
        record.buyerAddress ?? null,
        record.objectKey,
        record.objectDigest,
        record.envelopeObjectKey ?? null,
        record.envelopeDigest ?? null,
        JSON.stringify(record.commitments),
        JSON.stringify(record.policy),
        record.buyerPublicKey ?? null,
        record.buyerKeyField ?? null,
        JSON.stringify(record.secretMaterial),
      ]
    );
    return result.rows[0];
  }

  async function updateListing(id, patch) {
    const allowed = new Map([
      ["state", "state"],
      ["buyerAddress", "buyer_address"],
      ["buyerPublicKey", "buyer_public_key"],
      ["buyerKeyField", "buyer_key_field"],
      ["envelopeObjectKey", "envelope_object_key"],
      ["envelopeDigest", "envelope_digest"],
      ["secretMaterial", "secret_material"],
    ]);
    const sets = [];
    const values = [String(id)];
    for (const [key, value] of Object.entries(patch)) {
      const column = allowed.get(key);
      if (!column) throw new Error(`unsupported listing field: ${key}`);
      values.push(key === "secretMaterial" ? JSON.stringify(value) : value);
      const cast = key === "secretMaterial" ? "::jsonb" : "";
      sets.push(`${column} = $${values.length}${cast}`);
    }
    if (sets.length === 0) return getListing(id);
    sets.push("updated_at = now()");
    const result = await query(
      `UPDATE listings SET ${sets.join(", ")} WHERE chain_listing_id = $1 RETURNING *`,
      values
    );
    return result.rows[0] ?? null;
  }

  async function getListing(id) {
    const result = await query(
      `SELECT * FROM listings WHERE chain_listing_id = $1`,
      [String(id)]
    );
    return result.rows[0] ?? null;
  }

  async function listListings(limit = 100) {
    const result = await query(
      `SELECT * FROM listings ORDER BY chain_listing_id DESC LIMIT $1`,
      [limit]
    );
    return result.rows;
  }

  async function getBlock(number) {
    const result = await query(`SELECT * FROM chain_blocks WHERE block_number = $1`, [String(number)]);
    return result.rows[0] ?? null;
  }

  async function saveBlock(block) {
    await query(
      `INSERT INTO chain_blocks (block_number, block_hash, parent_hash, block_timestamp)
       VALUES ($1, $2, $3, to_timestamp($4))
       ON CONFLICT (block_number) DO UPDATE SET
          block_hash = EXCLUDED.block_hash,
          parent_hash = EXCLUDED.parent_hash,
          block_timestamp = EXCLUDED.block_timestamp`,
      [String(block.number), block.hash, block.parentHash, Number(block.timestamp)]
    );
  }

  async function saveEvent(event) {
    await query(
      `INSERT INTO chain_events (
          block_number, block_hash, transaction_hash, log_index,
          event_name, listing_id, tid, payload
       ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
       ON CONFLICT (transaction_hash, log_index) DO NOTHING`,
      [
        String(event.blockNumber),
        event.blockHash,
        event.transactionHash,
        event.index,
        event.eventName,
        event.listingId == null ? null : String(event.listingId),
        event.tid ?? null,
        JSON.stringify(event.payload),
      ]
    );
  }

  async function rollbackFromBlock(number) {
    await transaction(async (client) => {
      await client.query(`DELETE FROM chain_events WHERE block_number >= $1`, [String(number)]);
      await client.query(`DELETE FROM chain_blocks WHERE block_number >= $1`, [String(number)]);
      await client.query(
        `UPDATE indexer_checkpoint SET next_block = LEAST(next_block, $1), updated_at = now() WHERE singleton = true`,
        [String(number)]
      );
    });
  }

  async function getCheckpoint(defaultBlock = 0n) {
    const result = await query(`SELECT next_block FROM indexer_checkpoint WHERE singleton = true`);
    if (result.rowCount === 0) {
      await query(
        `INSERT INTO indexer_checkpoint (singleton, next_block) VALUES (true, $1)
         ON CONFLICT (singleton) DO NOTHING`,
        [String(defaultBlock)]
      );
      return BigInt(defaultBlock);
    }
    return BigInt(result.rows[0].next_block);
  }

  async function setCheckpoint(nextBlock) {
    await query(
      `INSERT INTO indexer_checkpoint (singleton, next_block)
       VALUES (true, $1)
       ON CONFLICT (singleton) DO UPDATE SET next_block = EXCLUDED.next_block, updated_at = now()`,
      [String(nextBlock)]
    );
  }

  return Object.freeze({
    pool,
    query,
    transaction,
    claimIdempotency,
    completeIdempotency,
    failIdempotency,
    saveListing,
    updateListing,
    getListing,
    listListings,
    getBlock,
    saveBlock,
    saveEvent,
    rollbackFromBlock,
    getCheckpoint,
    setCheckpoint,
    close: () => pool.end(),
  });
}
