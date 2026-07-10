CREATE TABLE IF NOT EXISTS api_idempotency (
    idempotency_key TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PROCESSING', 'COMPLETED', 'FAILED')),
    response JSONB,
    tx_hash TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS listings (
    chain_listing_id BIGINT PRIMARY KEY,
    tid TEXT NOT NULL UNIQUE,
    state SMALLINT NOT NULL,
    seller_address TEXT NOT NULL,
    buyer_address TEXT,
    object_key TEXT NOT NULL,
    object_digest TEXT NOT NULL,
    envelope_object_key TEXT,
    envelope_digest TEXT,
    commitments JSONB NOT NULL,
    policy JSONB NOT NULL,
    buyer_public_key TEXT,
    buyer_key_field NUMERIC(78, 0),
    secret_material JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS listings_state_idx ON listings(state);
CREATE INDEX IF NOT EXISTS listings_tid_idx ON listings(tid);

CREATE TABLE IF NOT EXISTS chain_blocks (
    block_number BIGINT PRIMARY KEY,
    block_hash TEXT NOT NULL UNIQUE,
    parent_hash TEXT NOT NULL,
    block_timestamp TIMESTAMPTZ NOT NULL,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_events (
    id BIGSERIAL PRIMARY KEY,
    block_number BIGINT NOT NULL,
    block_hash TEXT NOT NULL,
    transaction_hash TEXT NOT NULL,
    log_index INTEGER NOT NULL,
    event_name TEXT NOT NULL,
    listing_id BIGINT,
    tid TEXT,
    payload JSONB NOT NULL,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (transaction_hash, log_index)
);

CREATE INDEX IF NOT EXISTS chain_events_block_idx ON chain_events(block_number);
CREATE INDEX IF NOT EXISTS chain_events_listing_idx ON chain_events(listing_id);
CREATE INDEX IF NOT EXISTS chain_events_tid_idx ON chain_events(tid);

CREATE TABLE IF NOT EXISTS indexer_checkpoint (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    next_block BIGINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
