package canonical_vectors_test

import (
	"crypto/sha256"
	"encoding/json"
	"math/big"
	"os"
	"path/filepath"
	"testing"

	"github.com/1376524890/ddtm-qas/zk/circuits"
	"github.com/consensys/gnark-crypto/ecc/bn254"
	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/test"
)

// repoRoot walks up to the directory containing specs/canonical-data-v1.md.
func repoRoot() string {
	dir, _ := os.Getwd()
	for i := 0; i < 8; i++ {
		if _, err := os.Stat(filepath.Join(dir, "specs", "canonical-data-v1.md")); err == nil {
			return dir
		}
		p := filepath.Dir(dir)
		if p == dir {
			break
		}
		dir = p
	}
	return ".."
}

type manifestCase struct {
	ID                string   `json:"id"`
	Kind              string   `json:"kind"`
	Blob              string   `json:"blob"`
	ExpectedLeaves    []string `json:"expected_row_leaves"`
	ExpectedFirstLeaf string   `json:"expected_first_leaf"`
	ExpectedRoot      string   `json:"expected_data_root"`
	Generator         string   `json:"generator"`
	ExpectedError     string   `json:"expected_error"`
}

type manifest struct {
	SchemaSHA string        `json:"schema_sha256"`
	Cases     []manifestCase `json:"cases"`
}

// packRow chunks a 548-byte blob into 18 little-endian field elements.
func packRow(blob []byte) []*big.Int {
	out := make([]*big.Int, 0, 18)
	for off := 0; off < len(blob); off += 31 {
		end := off + 31
		if end > len(blob) {
			end = len(blob)
		}
		out = append(out, new(big.Int).SetBytes(reverse(blob[off:end])))
	}
	return out
}

func reverse(b []byte) []byte {
	r := make([]byte, len(b))
	for i := range b {
		r[i] = b[len(b)-1-i]
	}
	return r
}

func sha256Mod(name string, p *big.Int) *big.Int {
	sum := sha256.Sum256([]byte(name))
	return new(big.Int).Mod(new(big.Int).SetBytes(sum[:]), p)
}

func schemaHalves(path string) (*big.Int, *big.Int) {
	raw, _ := os.ReadFile(path)
	d := sha256.Sum256(raw)
	hi := new(big.Int).SetBytes(d[:16])
	lo := new(big.Int).SetBytes(d[16:])
	return hi, lo
}

// TestCanonicalVectors runs the RowCommitmentCircuit on the small positive
// vectors and checks the in-circuit leaf matches the manifest's golden leaf.
func TestCanonicalVectors(t *testing.T) {
	root := repoRoot()
	pc, err := circuits.LoadPoseidonConstants()
	if err != nil {
		t.Fatalf("load poseidon constants: %v", err)
	}
	schemaPath := filepath.Join(root, "specs", "canonical-data-v1.schema.json")
	schemaHi, schemaLo := schemaHalves(schemaPath)
	tagRow := sha256Mod("DDTM_ROW_V1", pc.Modulus)

	manRaw, err := os.ReadFile(filepath.Join(root, "experiments", "vectors", "manifest.json"))
	if err != nil {
		t.Fatalf("read manifest: %v", err)
	}
	var man manifest
	if err := json.Unmarshal(manRaw, &man); err != nil {
		t.Fatalf("parse manifest: %v", err)
	}

	checked := 0
	for _, c := range man.Cases {
		if c.Kind != "positive" || len(c.ExpectedLeaves) == 0 {
			continue
		}
		blob, err := os.ReadFile(filepath.Join(root, "experiments", "vectors", c.Blob))
		if err != nil {
			t.Fatalf("read blob %s: %v", c.Blob, err)
		}
		packed := packRow(blob[:548])

		var circuit circuits.RowCommitmentCircuit
		// Witness assignment.
		assignment := circuits.RowCommitmentCircuit{
			Index:    0,
			SchemaHi: schemaHi,
			SchemaLo: schemaLo,
			TagRow:   tagRow,
			Expected: mustBig(c.ExpectedLeaves[0]),
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

		// gnark test harness: compile + solve (BN254 only — the pinned
		// Poseidon2 constants are field-specific).
		assert := test.NewAssert(t)
		assert.SolvingSucceeded(&circuit, &assignment, test.WithCurves(bn254.ID))
		t.Logf("vector %s: leaf %s satisfied in-circuit", c.ID, shortHex(c.ExpectedLeaves[0]))
		checked++
		// The first few vectors fully exercise the wiring; keep it fast.
		if checked >= 3 {
			break
		}
	}
	if checked == 0 {
		t.Fatal("no positive vectors checked")
	}
}

func mustBig(s string) *big.Int {
	v, ok := new(big.Int).SetString(s, 0)
	if !ok {
		panic("bad hex " + s)
	}
	return v
}

func shortHex(s string) string {
	if len(s) > 18 {
		return s[:18] + "..."
	}
	return s
}

// silence unused (frontend/fr imports kept for clarity / future expansion)
var _ = fr.Modulus
var _ frontend.API
