# V1 network model

Hardhat provides deterministic local EVM execution and one-confirmation test finality. The gateway nevertheless treats transaction submission, receipt observation and event indexing as separate steps, applies bounded retry only to transient failures and records block ancestry. This keeps the application architecture compatible with a later public-EVM or consortium adapter while avoiding claims about real multi-node consensus in V1.
