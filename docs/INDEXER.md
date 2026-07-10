# Event indexer

The indexer polls only the configured safe height, stores block ancestry, deduplicates logs by transaction hash and log index, and updates the local listing state from the authoritative contract. If a stored block hash or parent differs from the provider's canonical block, it removes affected blocks and logs, rewinds the checkpoint and replays.
