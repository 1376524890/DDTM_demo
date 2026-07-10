# Circuit versioning

The V1 manifest identifies the protocol version, curve, proof system, constraint count and hashes of R1CS, proving key and verifying key. Deployment manifests identify verifier addresses. Any circuit change requires regenerated keys, verifier contracts, deployment metadata and test results; proofs from another version must not be accepted under the same deployment.
