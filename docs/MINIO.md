# MinIO integration

Every uploaded object receives a SHA-256 metadata value. The adapter immediately reads object metadata after upload and recomputes SHA-256 on retrieval. Ciphertext, key-envelope and evidence object keys are deterministic or content-derived to make retries safe and audit records reproducible.
