package canonical

import (
	"fmt"
	"math/big"

	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
)

const (
	rowBytes     = 548
	packChunk    = 31
	packedCount  = 18 // ceil(548/31)
	TreeDepth    = 17
	TreeCapacity = 1 << TreeDepth
)

// Context bundles the frozen schema halves + domain tags + poseidon instance
// so every leaf/node computation uses identical inputs.
type Context struct {
	P          *Poseidon
	SchemaHi   fr.Element
	SchemaLo   fr.Element
	TagRow     fr.Element
	TagPadding fr.Element
	TagNode    fr.Element
}

// PackRowFields splits a 548-byte blob into 18 field elements. Each chunk is
// interpreted as a little-endian integer (matching the Python reference's
// int.from_bytes(..., "little")); the final 21-byte chunk is taken at natural
// length (no zero padding — for little-endian the missing high bytes are 0).
func PackRowFields(blob []byte) ([]fr.Element, error) {
	if len(blob) != rowBytes {
		return nil, fmt.Errorf("expected %d-byte row", rowBytes)
	}
	out := make([]fr.Element, 0, packedCount)
	for offset := 0; offset < len(blob); offset += packChunk {
		end := offset + packChunk
		if end > len(blob) {
			end = len(blob)
		}
		chunk := blob[offset:end]
		rev := make([]byte, len(chunk)) // reverse: little-endian -> big-endian for SetBytes
		for i := range chunk {
			rev[i] = chunk[len(chunk)-1-i]
		}
		var e fr.Element
		e.SetBigInt(new(big.Int).SetBytes(rev))
		out = append(out, e)
	}
	return out, nil
}

// RowLeaf = H_P(TAG_ROW, [schemaHi, schemaLo, index, packed...])
func (c *Context) RowLeaf(index uint64, blob []byte) (fr.Element, error) {
	packed, err := PackRowFields(blob)
	if err != nil {
		return fr.Element{}, err
	}
	elements := make([]fr.Element, 0, 3+len(packed))
	elements = append(elements, c.SchemaHi, c.SchemaLo)
	var idx fr.Element
	idx.SetUint64(index)
	elements = append(elements, idx)
	elements = append(elements, packed...)
	return c.P.HashPoseidon(c.TagRow, elements), nil
}

// PaddingLeaf = H_P(TAG_PADDING, [schemaHi, schemaLo, index])
func (c *Context) PaddingLeaf(index uint64) fr.Element {
	var idx fr.Element
	idx.SetUint64(index)
	return c.P.HashPoseidon(c.TagPadding,
		[]fr.Element{c.SchemaHi, c.SchemaLo, idx})
}

// NodeHash = H_P(TAG_NODE, [level, left, right])
func (c *Context) NodeHash(level int, left, right fr.Element) fr.Element {
	var lvl fr.Element
	lvl.SetUint64(uint64(level))
	return c.P.HashPoseidon(c.TagNode, []fr.Element{lvl, left, right})
}

// BuildRoot builds the Merkle root for blobs padded up to capacity leaves.
func (c *Context) BuildRoot(blobs [][]byte, capacity int) (fr.Element, error) {
	if len(blobs) > capacity {
		return fr.Element{}, fmt.Errorf("row count %d exceeds capacity %d", len(blobs), capacity)
	}
	leaves := make([]fr.Element, capacity)
	for i, b := range blobs {
		leaf, err := c.RowLeaf(uint64(i), b)
		if err != nil {
			return fr.Element{}, err
		}
		leaves[i] = leaf
	}
	for i := len(blobs); i < capacity; i++ {
		leaves[i] = c.PaddingLeaf(uint64(i))
	}

	level := 0
	for len(leaves) > 1 {
		next := make([]fr.Element, len(leaves)/2)
		for i := 0; i < len(leaves); i += 2 {
			next[i/2] = c.NodeHash(level, leaves[i], leaves[i+1])
		}
		leaves = next
		level++
	}
	return leaves[0], nil
}

// GeneratedFeatures reproduces the synthetic-v1 deterministic feature vector.
// Must match Python experiments/g1/generate_vectors.generated_features.
func GeneratedFeatures(i int) [FeatureCount]int32 {
	var out [FeatureCount]int32
	for j := 0; j < FeatureCount; j++ {
		out[j] = int32(((i + 1) * (j + 1)) & 0xFFFF)
	}
	return out
}

// EncodeGeneratedRow builds the encoded blob for synthetic-v1 row i.
func EncodeGeneratedRow(i int) ([]byte, error) {
	row := &Row{
		RowID:       uint64(i),
		Timestamp:   uint64(1700000000 + i),
		Features:    GeneratedFeatures(i),
		MissingMask: [MaskSize]byte{},
		Label:       1,
		Valid:       1,
	}
	if i%2 != 0 {
		row.Label = -1
	}
	return row.Encode()
}

// HexElement renders a field element as 0x-prefixed lowercase canonical hex.
func HexElement(e fr.Element) string {
	bi := e.BigInt(new(big.Int))
	return "0x" + bi.Text(16)
}
