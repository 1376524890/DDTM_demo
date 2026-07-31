package merkle

import (
	"math/big"
	"testing"

	"github.com/1376524890/ddtm-qas/canonicalizer/internal/codec"
)

func makeRow(id uint64, label int8, feat int32) codec.Row {
	var row codec.Row
	row.Version = codec.RowVersion
	row.RowID = id
	row.Valid = 1
	row.Label = label
	row.Timestamp = 1700000000
	for i := range row.Features {
		row.Features[i] = feat
	}
	return row
}

func TestLeafDeterministic(t *testing.T) {
	schemaHash := big.NewInt(12345)
	version := big.NewInt(1)
	row := makeRow(0, 1, 65536)
	l1, err := Leaf(row, schemaHash, version)
	if err != nil {
		t.Fatal(err)
	}
	l2, err := Leaf(row, schemaHash, version)
	if err != nil {
		t.Fatal(err)
	}
	if l1.Cmp(l2) != 0 {
		t.Fatal("leaf not deterministic")
	}
}

func TestLeafBitSensitive(t *testing.T) {
	schemaHash := big.NewInt(12345)
	version := big.NewInt(1)
	row := makeRow(0, 1, 65536)
	l1, _ := Leaf(row, schemaHash, version)
	row.Features[0] = 65537
	l2, _ := Leaf(row, schemaHash, version)
	if l1.Cmp(l2) == 0 {
		t.Fatal("bit flip should change leaf")
	}
}

func TestLeafRowIdSensitive(t *testing.T) {
	schemaHash := big.NewInt(12345)
	version := big.NewInt(1)
	row1 := makeRow(0, 1, 65536)
	row2 := makeRow(1, 1, 65536)
	l1, _ := Leaf(row1, schemaHash, version)
	l2, _ := Leaf(row2, schemaHash, version)
	if l1.Cmp(l2) == 0 {
		t.Fatal("row_id change should change leaf")
	}
}

func TestLeafSchemaSensitive(t *testing.T) {
	row := makeRow(0, 1, 65536)
	s1 := big.NewInt(12345)
	s2 := big.NewInt(12346)
	l1, _ := Leaf(row, s1, big.NewInt(1))
	l2, _ := Leaf(row, s2, big.NewInt(1))
	if l1.Cmp(l2) == 0 {
		t.Fatal("schema change should change leaf")
	}
}

func TestPaddingLeafDeterministic(t *testing.T) {
	schema := big.NewInt(12345)
	version := big.NewInt(1)
	p1, _ := PaddingLeaf(131071, schema, version)
	p2, _ := PaddingLeaf(131071, schema, version)
	if p1.Cmp(p2) != 0 {
		t.Fatal("padding leaf not deterministic")
	}
}

func TestTreeBuildAndRoot(t *testing.T) {
	schemaHash := big.NewInt(12345)
	version := big.NewInt(1)
	leaves := make([]*big.Int, TreeCapacity)
	for i := 0; i < TreeCapacity; i++ {
		if i < 100 {
			row := makeRow(uint64(i), 1, int32(65536+int64(i)*100))
			leaf, err := Leaf(row, schemaHash, version)
			if err != nil {
				t.Fatal(err)
			}
			leaves[i] = leaf
		} else {
			leaf, err := PaddingLeaf(uint64(i), schemaHash, version)
			if err != nil {
				t.Fatal(err)
			}
			leaves[i] = leaf
		}
	}

	tree, err := Build(leaves)
	if err != nil {
		t.Fatal(err)
	}
	root := tree.Root()
	if root == nil || root.Sign() == 0 {
		t.Fatal("root must be non-zero")
	}

	// Rebuild must produce same root.
	tree2, _ := Build(leaves)
	if tree.Root().Cmp(tree2.Root()) != 0 {
		t.Fatal("rebuild must produce same root")
	}
}

func TestMerklePathVerify(t *testing.T) {
	schemaHash := big.NewInt(12345)
	version := big.NewInt(1)
	leaves := make([]*big.Int, TreeCapacity)
	for i := 0; i < TreeCapacity; i++ {
		if i < 100 {
			row := makeRow(uint64(i), 1, int32(65536+int64(i)*100))
			leaf, _ := Leaf(row, schemaHash, version)
			leaves[i] = leaf
		} else {
			leaf, _ := PaddingLeaf(uint64(i), schemaHash, version)
			leaves[i] = leaf
		}
	}

	tree, _ := Build(leaves)

	// Verify path for row 0
	path, err := tree.Path(0)
	if err != nil {
		t.Fatal(err)
	}
	if len(path) != TreeDepth {
		t.Fatalf("expected %d siblings, got %d", TreeDepth, len(path))
	}

	// Manually compute root from leaf and path.
	current := leaves[0]
	for level := 0; level < TreeDepth; level++ {
		bit := (0 >> level) & 1
		var left, right *big.Int
		if bit == 0 {
			left = current
			right = path[level]
		} else {
			left = path[level]
			right = current
		}
		next, err := Node(level, left, right)
		if err != nil {
			t.Fatal(err)
		}
		current = next
	}

	if current.Cmp(tree.Root()) != 0 {
		t.Fatal("Merkle path verification failed")
	}
}

func TestMerklePathWrongIndex(t *testing.T) {
	schemaHash := big.NewInt(12345)
	version := big.NewInt(1)
	leaves := make([]*big.Int, TreeCapacity)
	for i := 0; i < TreeCapacity; i++ {
		leaf, _ := PaddingLeaf(uint64(i), schemaHash, version)
		leaves[i] = leaf
	}
	tree, _ := Build(leaves)

	path, _ := tree.Path(0)
	// Use leaf[1] with path[0] — should not match.
	current := leaves[1]
	for level := 0; level < TreeDepth; level++ {
		bit := (0 >> level) & 1
		var left, right *big.Int
		if bit == 0 {
			left = current
			right = path[level]
		} else {
			left = path[level]
			right = current
		}
		next, _ := Node(level, left, right)
		current = next
	}
	if current.Cmp(tree.Root()) == 0 {
		t.Fatal("wrong leaf should not verify")
	}
}

func TestRowSwapChangesRoot(t *testing.T) {
	schemaHash := big.NewInt(12345)
	version := big.NewInt(1)
	makeLeaves := func() []*big.Int {
		leaves := make([]*big.Int, TreeCapacity)
		row0 := makeRow(0, 1, 65536)
		row1 := makeRow(1, -1, 131072)
		l0, _ := Leaf(row0, schemaHash, version)
		l1, _ := Leaf(row1, schemaHash, version)
		leaves[0] = l0
		leaves[1] = l1
		for i := 2; i < TreeCapacity; i++ {
			l, _ := PaddingLeaf(uint64(i), schemaHash, version)
			leaves[i] = l
		}
		return leaves
	}

	tree1, _ := Build(makeLeaves())

	// Swap
	swapped := makeLeaves()
	swapped[0], swapped[1] = swapped[1], swapped[0]
	tree2, _ := Build(swapped)

	if tree1.Root().Cmp(tree2.Root()) == 0 {
		t.Fatal("row swap should change root")
	}
}
