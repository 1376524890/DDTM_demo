# Finality handling

The local reference environment uses one Hardhat confirmation. The adapter exposes a configurable confirmation count, and the indexer processes only blocks at or below the configured safe height. Stored parent hashes permit rollback if a future EVM deployment presents a different canonical chain.
