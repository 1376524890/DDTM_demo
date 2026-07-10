# Continuous integration

The V1 workflow has three independent jobs:

1. Circuit tests, trusted setup, verifier generation and real-proof Hardhat tests.
2. Gateway syntax and Node.js unit tests.
3. Docker Compose schema validation and required-path checks.

The first job uploads the circuit manifest and generated verifier contracts as a workflow artifact.
