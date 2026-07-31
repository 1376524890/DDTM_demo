# Canonical Data Format v1 (DDTM-CANONICAL-V1)

This is the **single source of truth** for the deterministic data layer. Every
language (Python, Go, Rust, gnark) MUST produce byte-identical row encodings,
identical Poseidon2 leaves, and an identical Merkle `dataRoot` for the same
inputs. The normative artifacts live next to this document:

| Artifact | Purpose |
|---|---|
| `canonical-data-v1.schema.json` | Frozen schema; its **raw bytes** define the SchemaHash |
| `row-layout-v1.json` | Exact 548-byte row layout |
| `poseidon2-bn254-v1.json` | Pinned Poseidon2 BN254 width-4 constants + KAT |
| `domain-tags-v1.json` | Domain-separation tags |
| `error-codes-v1.json` | Canonical rejection codes |

> The `schema_sha256` is `SHA-256` of the raw UTF-8 / LF bytes of
> `canonical-data-v1.schema.json`. It is split into `schemaHi` (first 16 bytes,
> big-endian) and `schemaLo` (last 16 bytes). No language may reformat the file
> before hashing.

## 1. Row layout (548 bytes, little-endian)

| Offset | Size | Field | Constraint |
|---:|---:|---|---|
| 0 | 8 | `row_id : uint64` | `>= 0`; data row == physical index; padding == leaf index |
| 8 | 8 | `timestamp : uint64` | `>= 0`; Unix seconds; `0` for padding |
| 16 | 512 | `features[128] : int32` | Q16.16 fixed-point |
| 528 | 16 | `missing_mask[16]` | bit `k` set ⇒ feature `k` missing |
| 544 | 1 | `label : int8` | data: `-1` or `+1`; padding: `-1` |
| 545 | 1 | `valid : uint8` | data: `1`; padding: `0` |
| 546 | 2 | `reserved : uint16` | MUST be `0` |

## 2. Quantization: IEEE-754 float32 → Q16.16

1. Read the **float32 bit pattern** (`NaN`/`+Inf`/`-Inf` ⇒ **`NON_FINITE_FEATURE`**, rejected — never clamped).
2. Decode sign/exponent/mantissa into the exact integer value `mantissa * 2^e`.
3. Convert to Q16.16 by a **ties-to-even** multiply/shift, then clamp to
   `[lower_q16, upper_q16] = [-2^31, 2^31-1]`.

Implementations MUST use the integer bit decomposition; language defaults such
as `math.Round` are NOT ties-to-even and are forbidden. A missing feature uses
`q16 = 0` and sets the corresponding mask bit.

## 3. Schema hash and domain tags

```
schemaDigest = SHA-256(canonical-data-v1.schema.json raw bytes)
schemaHi = int.from_bytes(schemaDigest[0:16],  "big")
schemaLo = int.from_bytes(schemaDigest[16:32], "big")

TAG_X = int.from_bytes(SHA-256("DDTM_X_V1"), "big") mod p
```

## 4. Field packing (row → 18 field elements)

The 548-byte row blob is split into 31-byte little-endian chunks:
`ceil(548/31) = 18` elements. 31 bytes fits below the BN254 scalar, so each
chunk is a unique field element with no modular-reduction ambiguity.

## 5. Poseidon2 sponge `H_P`

Poseidon2 BN254 **width 4** (8 full + 56 partial rounds, s-box `x^5`), with the
pinned constants from `poseidon2-bn254-v1.json`. `H_P(tag, elements)` absorbs
the message `[tag, len(elements), *elements]` through a rate-3 sponge (initial
state all zero, final block zero-padded) and squeezes element 0. The explicit
arity field prevents length-extension ambiguity.

## 6. Leaves and nodes

```
row_leaf_i     = H_P(TAG_ROW,     [schemaHi, schemaLo, i, r0 .. r17])   # arity 21
padding_leaf_i = H_P(TAG_PADDING, [schemaHi, schemaLo, i])              # arity 3
node(level,L,R)= H_P(TAG_NODE,    [level, L, R])                       # arity 3
```

The tree has depth 17 (capacity `2^17 = 131072`). Real rows fill the low
indices; the remainder is `padding_leaf`. `level` participates in the node hash
to remove cross-level ambiguity.

## 7. Negative inputs

`NaN`, `+Inf`, `-Inf` are rejected with `NON_FINITE_FEATURE`. Negative test
vectors do not produce a `.bin`; they assert the canonicalizer rejects them with
the recorded code.
