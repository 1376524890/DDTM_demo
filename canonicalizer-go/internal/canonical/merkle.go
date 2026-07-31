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

// Context 把冻结的 schema 两半 + 域标签 + poseidon 实例绑在一起，使每个叶子/节点
// 计算都用相同的输入。
type Context struct {
	P          *Poseidon
	SchemaHi   fr.Element
	SchemaLo   fr.Element
	TagRow     fr.Element
	TagPadding fr.Element
	TagNode    fr.Element
}

// PackRowFields 把 548 字节 blob 拆成 18 个域元素（31 字节小端）。
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
		rev := make([]byte, len(chunk)) // 反转：小端 → 大端，供 SetBytes 使用
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

// BuildRoot 为 blobs（padding 到 capacity 叶子）构建 Merkle 根。
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

// GeneratedFeatures 重现 synthetic-v1 的确定性特征向量。
// 必须与 Python experiments/g1/generate_vectors.generated_features 一致。
func GeneratedFeatures(i int) [FeatureCount]int32 {
	var out [FeatureCount]int32
	for j := 0; j < FeatureCount; j++ {
		out[j] = int32(((i + 1) * (j + 1)) & 0xFFFF)
	}
	return out
}

// EncodeGeneratedRow 为 synthetic-v1 的第 i 行构造已编码 blob。
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

// HexElement 把域元素渲染为 0x 前缀的小写规范十六进制。
func HexElement(e fr.Element) string {
	bi := e.BigInt(new(big.Int))
	return "0x" + bi.Text(16)
}
