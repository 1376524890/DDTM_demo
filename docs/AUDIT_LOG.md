# Audit records

The system preserves contract events, transaction hashes, block hashes, object digests, proof hashes, request IDs, evidence hashes and terminal decisions. PostgreSQL is an index and recovery aid; authoritative settlement state remains in the contract, while authoritative artifact bytes remain digest-addressed in MinIO.
