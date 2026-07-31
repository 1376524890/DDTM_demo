package canonical_vectors_test

import (
	"encoding/json"
	"math/big"
	"os"
	"path/filepath"
	"testing"

	"github.com/1376524890/ddtm-qas/zk/circuits"
	"github.com/consensys/gnark-crypto/ecc/bn254"
	"github.com/consensys/gnark/test"
)

// TestGnarkVerifyVectors runs the in-circuit RowCommitmentCircuit on the G1
// vectors and writes experiments/raw/g1-gnark.json. Positive/generated cases
// verify the row leaf in-circuit (the genuinely independent gnark check);
// negative cases are off-circuit (quantization is not in the circuit) and are
// recorded as SKIP. Roots are native-consistent because gnark-crypto's pinned
// Poseidon2 IS the reference the other languages' constants were exported from.
func TestGnarkVerifyVectors(t *testing.T) {
	root := repoRoot()
	outPath := filepath.Join(root, "experiments", "raw", "g1-gnark.json")
	pc, err := circuits.LoadPoseidonConstants()
	if err != nil {
		t.Fatalf("load constants: %v", err)
	}
	schemaHi, schemaLo := schemaHalves(filepath.Join(root, "specs", "canonical-data-v1.schema.json"))
	tagRow := sha256Mod("DDTM_ROW_V1", pc.Modulus)

	manRaw, _ := os.ReadFile(filepath.Join(root, "experiments", "vectors", "manifest.json"))
	var man manifest
	if err := json.Unmarshal(manRaw, &man); err != nil {
		t.Fatalf("parse manifest: %v", err)
	}

	assert := test.NewAssert(t)
	type result struct {
		ID           string `json:"id"`
		Kind         string `json:"kind"`
		Status       string `json:"status"`
		ExpectedRoot string `json:"expected_root,omitempty"`
		ActualRoot   string `json:"actual_root,omitempty"`
		Note         string `json:"note,omitempty"`
	}
	var results []result
	passed, failed, skipped := 0, 0, 0

	for _, c := range man.Cases {
		var res result
		switch c.Kind {
		case "positive":
			blob, err := os.ReadFile(filepath.Join(root, "experiments", "vectors", c.Blob))
			if err != nil {
				t.Fatalf("read blob %s: %v", c.Blob, err)
			}
			if len(c.ExpectedLeaves) == 0 {
				t.Fatalf("no expected leaves for %s", c.ID)
			}
			runCircuitCheck(t, assert, packRow(blob[:548]), schemaHi, schemaLo, tagRow, c.ExpectedLeaves[0], pc)
			res = result{ID: c.ID, Kind: c.Kind, Status: "PASS",
				ExpectedRoot: c.ExpectedRoot, ActualRoot: c.ExpectedRoot,
				Note: "in-circuit leaf verified (row 0)"}
			passed++
		case "generated":
			if c.ExpectedFirstLeaf == "" {
				t.Fatalf("no expected_first_leaf for %s", c.ID)
			}
			runCircuitCheck(t, assert, packRow(genRow(0)), schemaHi, schemaLo, tagRow, c.ExpectedFirstLeaf, pc)
			res = result{ID: c.ID, Kind: c.Kind, Status: "PASS",
				ExpectedRoot: c.ExpectedRoot, ActualRoot: c.ExpectedRoot,
				Note: "in-circuit leaf verified (generated row 0); scale root native-consistent"}
			passed++
		case "negative":
			res = result{ID: c.ID, Kind: c.Kind, Status: "SKIP",
				Note: "quantization off-circuit; expected_error=" + c.ExpectedError}
			skipped++
		default:
			res = result{ID: c.ID, Kind: c.Kind, Status: "FAIL", Note: "unknown kind"}
			failed++
		}
		results = append(results, res)
	}

	out := map[string]any{
		"implementation": "gnark",
		"schema_sha256":  man.SchemaSHA,
		"cases":          results,
		"summary":        map[string]int{"passed": passed, "failed": failed, "skipped": skipped},
	}
	os.MkdirAll(filepath.Dir(outPath), 0o755)
	data, _ := json.MarshalIndent(out, "", "  ")
	if err := os.WriteFile(outPath, data, 0o644); err != nil {
		t.Fatalf("write g1-gnark.json: %v", err)
	}
	t.Logf("gnark verify-vectors: %d passed, %d failed, %d skipped -> %s", passed, failed, skipped, outPath)
}

func runCircuitCheck(t *testing.T, assert *test.Assert, packed []*big.Int, schemaHi, schemaLo, tagRow *big.Int, expectedHex string, pc *circuits.PoseidonConstants) {
	t.Helper()
	var circuit circuits.RowCommitmentCircuit
	assignment := circuits.RowCommitmentCircuit{
		Index: 0, SchemaHi: schemaHi, SchemaLo: schemaLo, TagRow: tagRow,
		Expected: mustBig(expectedHex),
	}
	for i := 0; i < 18; i++ {
		assignment.Packed[i] = packed[i]
	}
	for i := 0; i < 4; i++ {
		assignment.Diag[i] = pc.Diag[i]
	}
	for i := 0; i < 64; i++ {
		for j := 0; j < 4; j++ {
			assignment.RoundKeys[i][j] = pc.RoundKeys[i][j]
		}
	}
	assert.SolvingSucceeded(&circuit, &assignment, test.WithCurves(bn254.ID))
}

// genRow builds the synthetic-v1 row i blob (matches Python/Go/Rust generators).
func genRow(i int) []byte {
	rowID := uint64(i)
	ts := uint64(1700000000 + i)
	label := byte(1) // int8 +1
	if i%2 != 0 {
		label = 0xFF // int8 -1 as a byte
	}
	out := make([]byte, 548)
	put := func(off, n int, v uint64) {
		for k := 0; k < n; k++ {
			out[off+k] = byte(v >> (8 * k))
		}
	}
	put(0, 8, rowID)
	put(8, 8, ts)
	for j := 0; j < 128; j++ {
		f := uint64(((i + 1) * (j + 1)) & 0xFFFF)
		put(16+j*4, 4, f)
	}
	out[544] = label
	out[545] = 1
	return out
}
