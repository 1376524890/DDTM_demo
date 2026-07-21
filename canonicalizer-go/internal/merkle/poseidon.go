package merkle

import (
	"fmt"
	"math/big"

	"github.com/1376524890/ddtm-qas/canonicalizer/internal/codec"
	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	"github.com/consensys/gnark-crypto/ecc/bn254/fr/poseidon2"
)

const TreeDepth = 17
const TreeCapacity = 1 << TreeDepth

var (
	TagRow     = big.NewInt(0x44525401) // "DRT" + version
	TagNode    = big.NewInt(0x444E4401) // "DND" + version
	TagPadding = big.NewInt(0x44504401) // "DPD" + version
)

func hashElements(values ...*big.Int) (*big.Int, error) {
	h := poseidon2.NewMerkleDamgardHasher()
	for _, v := range values {
		if v.Sign() < 0 {
			return nil, fmt.Errorf("negative field input")
		}
		var e fr.Element
		e.SetBigInt(v)
		b := e.Bytes()
		if _, err := h.Write(b[:]); err != nil {
			return nil, err
		}
	}
	digest := h.Sum(nil)
	var out fr.Element
	if err := out.SetBytesCanonical(digest); err != nil {
		return nil, err
	}
	return out.BigInt(new(big.Int)), nil
}

func Leaf(row codec.Row, schemaHash, datasetVersion *big.Int) (*big.Int, error) {
	if err := row.Validate(); err != nil {
		return nil, err
	}
	lo, hi := codec.MaskLimbs(row.MissingMask)
	values := []*big.Int{
		TagRow,
		schemaHash,
		datasetVersion,
		new(big.Int).SetUint64(row.RowID),
		new(big.Int).SetUint64(uint64(row.Valid)),
		new(big.Int).SetUint64(codec.EncodeLabel(row.Label)),
		new(big.Int).SetUint64(row.Timestamp),
		new(big.Int).SetUint64(lo),
		new(big.Int).SetUint64(hi),
	}
	values = append(values, codec.PackFeatures(row.Features)...)
	return hashElements(values...)
}

func PaddingLeaf(index uint64, schemaHash, datasetVersion *big.Int) (*big.Int, error) {
	return hashElements(TagPadding, schemaHash, datasetVersion, new(big.Int).SetUint64(index))
}

func Node(level int, left, right *big.Int) (*big.Int, error) {
	return hashElements(TagNode, big.NewInt(int64(level)), left, right)
}

type Tree struct {
	Levels [][]*big.Int
}

func Build(leaves []*big.Int) (*Tree, error) {
	if len(leaves) != TreeCapacity {
		return nil, fmt.Errorf("need %d leaves", TreeCapacity)
	}
	levels := make([][]*big.Int, TreeDepth+1)
	levels[0] = leaves
	cur := leaves
	for level := 0; level < TreeDepth; level++ {
		next := make([]*big.Int, len(cur)/2)
		for i := 0; i < len(cur); i += 2 {
			n, err := Node(level, cur[i], cur[i+1])
			if err != nil {
				return nil, err
			}
			next[i/2] = n
		}
		levels[level+1] = next
		cur = next
	}
	return &Tree{Levels: levels}, nil
}

func (t *Tree) Root() *big.Int { return new(big.Int).Set(t.Levels[TreeDepth][0]) }

func (t *Tree) Path(index uint64) ([]*big.Int, error) {
	if index >= TreeCapacity {
		return nil, fmt.Errorf("index out of range")
	}
	path := make([]*big.Int, TreeDepth)
	x := int(index)
	for level := 0; level < TreeDepth; level++ {
		path[level] = new(big.Int).Set(t.Levels[level][x^1])
		x >>= 1
	}
	return path, nil
}
