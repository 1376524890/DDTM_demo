# Canonical Data Format v1

## Shape

- Maximum rows: 100,000.
- Merkle capacity: 131,072 (`2^17`).
- Logical feature dimension: 1-128.
- Physical feature dimension: exactly 128.
- Binary label: `-1` or `+1`.

## Row fields

| Field | Type | Constraint |
|---|---|---|
| version | uint16 | exactly 1 |
| row_id | uint64 | equals zero-based physical row index |
| valid | uint8 | 0 or 1 |
| label | int8 | -1 or +1 when valid; 0 when padding |
| timestamp | uint64 | Unix seconds |
| missing_mask | 16 bytes | bit k denotes missing feature k |
| features | 128 x int32 | Q16.16 fixed-point |

## Quantization

For a schema-defined offset `o`, scale `s > 0`, lower bound `l`, and upper bound `u`:

```
q = round_half_to_even((clip(x,l,u)-o)/s * 2^16)
```

`q` must fit signed int32. Missing values use `q=0` and must set the corresponding mask bit.

## Field packing

Seven signed int32 values are converted to unsigned offset representation and packed into one field element:

```
u_k = uint64(int64(q_k) + 2^31)
packed = sum(u_k << (32*k)), k=0..6
```

The top bits remain zero, so packed values are below `2^224` and safely below the BN254 scalar modulus.

## Leaf hash

```
leaf_i = Poseidon2(
  TAG_ROW_V1,
  schema_hash,
  dataset_version,
  row_id,
  valid,
  label_encoded,
  timestamp,
  missing_mask_lo,
  missing_mask_hi,
  packed_feature_0, ... packed_feature_18
)
```

`label_encoded` is 0 for padding, 1 for -1, and 2 for +1.

## Tree hash

```
node = Poseidon2(TAG_NODE_V1, level, left, right)
```

Padding leaves are deterministic hashes of `(TAG_PADDING_V1, schema_hash, dataset_version, index)`.
