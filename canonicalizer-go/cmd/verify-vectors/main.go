// Command verify-vectors 读取 G1 清单，用 Go 独立重新推导每一行叶子与 Merkle 根，
// 并与清单的 golden 值（由 Python 参考实现产出）比对。负向用例被重新量化，必须以
// 记录的错误码被拒绝。生成用例由 synthetic-v1 生成器重新物化并重新哈希。
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"os"
	"path/filepath"

	"github.com/1376524890/ddtm-qas/canonicalizer/internal/canonical"
	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
)

// 清单结构（对应 experiments/vectors/manifest.json）。
type manifestCase struct {
	ID             string   `json:"id"`
	Kind           string   `json:"kind"`
	RowCount       int      `json:"row_count"`
	Capacity       int      `json:"capacity"`
	Blob           string   `json:"blob"`
	BlobSHA256     string   `json:"blob_sha256"`
	ExpectedRoot   string   `json:"expected_data_root"`
	ExpectedLeaves []string `json:"expected_row_leaves"`
	ExpectedError  string   `json:"expected_error"`
	Input          string   `json:"input"`
	Generator      string   `json:"generator"`
	Seed           int      `json:"seed"`
}

type manifest struct {
	Protocol  string         `json:"protocol"`
	SchemaSHA string         `json:"schema_sha256"`
	SchemaHi  string         `json:"schema_hi"`
	SchemaLo  string         `json:"schema_lo"`
	Cases     []manifestCase `json:"cases"`
}

type caseResult struct {
	ID            string `json:"id"`
	Kind          string `json:"kind"`
	Status        string `json:"status"`
	ExpectedRoot  string `json:"expected_root,omitempty"`
	ActualRoot    string `json:"actual_root,omitempty"`
	ExpectedError string `json:"expected_error,omitempty"`
	ActualError   string `json:"actual_error,omitempty"`
	Note          string `json:"note,omitempty"`
}

type output struct {
	Implementation string       `json:"implementation"`
	SchemaSHA      string       `json:"schema_sha256"`
	Cases          []caseResult `json:"cases"`
	Summary        summary      `json:"summary"`
}

type summary struct {
	Passed int `json:"passed"`
	Failed int `json:"failed"`
}

// negativeDefinition 对应 experiments/vectors/definitions/<id>.json。
type negativeDefinition struct {
	ID  string `json:"id"`
	Row struct {
		Features        []interface{} `json:"features"`
		FeatureSentinel string        `json:"feature_sentinel"`
	} `json:"row"`
	ExpectedError string `json:"expected_error"`
}

func hex0x(x fr.Element) string { return canonical.HexElement(x) }

// repoRoot 向上查找含有 specs/canonical-data-v1.md 的目录。
func repoRoot() string {
	dir, _ := os.Getwd()
	for i := 0; i < 8; i++ {
		if _, err := os.Stat(filepath.Join(dir, "specs", "canonical-data-v1.md")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return "."
}

func main() {
	root := repoRoot()
	manifestPath := flag.String("manifest", filepath.Join(root, "experiments", "vectors", "manifest.json"), "manifest path")
	outPath := flag.String("output", filepath.Join(root, "experiments", "raw", "g1-go.json"), "output path")
	schemaPath := flag.String("schema", filepath.Join(root, "specs", "canonical-data-v1.schema.json"), "schema path")
	poseidonPath := flag.String("poseidon", filepath.Join(root, "specs", "poseidon2-bn254-v1.json"), "poseidon params")
	flag.Parse()

	// 加载钉定的 Poseidon2 + schema 上下文。
	p, err := canonical.LoadPoseidon(*poseidonPath)
	if err != nil {
		die("poseidon load: %v", err)
	}
	hi, lo, err := canonical.SchemaHalves(*schemaPath)
	if err != nil {
		die("schema load: %v", err)
	}
	tags := canonical.DomainTags(p.P)
	ctx := &canonical.Context{
		P: p, SchemaHi: hi, SchemaLo: lo,
		TagRow: tags["DDTM_ROW_V1"], TagPadding: tags["DDTM_PADDING_V1"],
		TagNode: tags["DDTM_NODE_V1"],
	}

	man, err := readManifest(*manifestPath)
	if err != nil {
		die("manifest read: %v", err)
	}

	var results []caseResult
	passed, failed := 0, 0
	for _, c := range man.Cases {
		var res caseResult
		switch c.Kind {
		case "positive":
			res = verifyPositive(ctx, c, filepath.Dir(*manifestPath))
		case "negative":
			res = verifyNegative(c, filepath.Dir(*manifestPath))
		case "generated":
			res = verifyGenerated(ctx, c)
		default:
			res = caseResult{ID: c.ID, Kind: c.Kind, Status: "FAIL", Note: "unknown kind"}
		}
		if res.Status == "PASS" {
			passed++
		} else {
			failed++
		}
		results = append(results, res)
	}

	out := output{
		Implementation: "go",
		SchemaSHA:      man.SchemaSHA,
		Cases:          results,
		Summary:        summary{Passed: passed, Failed: failed},
	}
	writeJSON(*outPath, out)
	fmt.Printf("go verify-vectors: %d passed, %d failed -> %s\n", passed, failed, *outPath)
	if failed > 0 {
		os.Exit(1)
	}
}

func verifyPositive(ctx *canonical.Context, c manifestCase, vectorsDir string) caseResult {
	blobPath := filepath.Join(vectorsDir, c.Blob)
	blob, err := os.ReadFile(blobPath)
	if err != nil {
		return fail(c, "read blob: %v", err)
	}
	if h := sha256hex(blob); h != c.BlobSHA256 {
		return fail(c, "blob sha256 mismatch: got %s", h)
	}
	rowCount := len(blob) / canonical.RowSize
	if rowCount != c.RowCount {
		return fail(c, "row count %d != %d", rowCount, c.RowCount)
	}
	leaves := make([]fr.Element, rowCount)
	blobs := make([][]byte, rowCount)
	for i := 0; i < rowCount; i++ {
		rowBlob := blob[i*canonical.RowSize : (i+1)*canonical.RowSize]
		if _, err := canonical.DecodeRow(rowBlob); err != nil {
			return fail(c, "decode row %d: %v", i, err)
		}
		leaf, err := ctx.RowLeaf(uint64(i), rowBlob)
		if err != nil {
			return fail(c, "leaf %d: %v", i, err)
		}
		leaves[i] = leaf
		blobs[i] = rowBlob
	}
	for i, wantHex := range c.ExpectedLeaves {
		if got := hex0x(leaves[i]); got != wantHex {
			return fail(c, "leaf %d mismatch: got %s want %s", i, got, wantHex)
		}
	}
	root, err := ctx.BuildRoot(blobs, c.Capacity)
	if err != nil {
		return fail(c, "build root: %v", err)
	}
	got := hex0x(root)
	if got != c.ExpectedRoot {
		return caseResult{ID: c.ID, Kind: c.Kind, Status: "FAIL",
			ExpectedRoot: c.ExpectedRoot, ActualRoot: got, Note: "root mismatch"}
	}
	return caseResult{ID: c.ID, Kind: c.Kind, Status: "PASS",
		ExpectedRoot: c.ExpectedRoot, ActualRoot: got}
}

func verifyNegative(c manifestCase, vectorsDir string) caseResult {
	defPath := filepath.Join(vectorsDir, c.Input)
	raw, err := os.ReadFile(defPath)
	if err != nil {
		return fail(c, "read def: %v", err)
	}
	var def negativeDefinition
	if err := json.Unmarshal(raw, &def); err != nil {
		return fail(c, "parse def: %v", err)
	}
	value := sentinelToFloat(def.Row.FeatureSentinel)
	_, qerr := canonical.Quantize(value)
	if qerr == nil {
		return caseResult{ID: c.ID, Kind: c.Kind, Status: "FAIL",
			ExpectedError: c.ExpectedError, Note: "expected rejection, got value"}
	}
	actual := errorCode(qerr)
	if actual != c.ExpectedError {
		return caseResult{ID: c.ID, Kind: c.Kind, Status: "FAIL",
			ExpectedError: c.ExpectedError, ActualError: actual}
	}
	return caseResult{ID: c.ID, Kind: c.Kind, Status: "PASS",
		ExpectedError: c.ExpectedError, ActualError: actual}
}

func verifyGenerated(ctx *canonical.Context, c manifestCase) caseResult {
	if c.Generator != "synthetic-v1" {
		return fail(c, "unknown generator %s", c.Generator)
	}
	blobs := make([][]byte, c.RowCount)
	for i := 0; i < c.RowCount; i++ {
		b, err := canonical.EncodeGeneratedRow(i)
		if err != nil {
			return fail(c, "encode generated row %d: %v", i, err)
		}
		blobs[i] = b
	}
	root, err := ctx.BuildRoot(blobs, c.Capacity)
	if err != nil {
		return fail(c, "build root: %v", err)
	}
	got := hex0x(root)
	if got != c.ExpectedRoot {
		return caseResult{ID: c.ID, Kind: c.Kind, Status: "FAIL",
			ExpectedRoot: c.ExpectedRoot, ActualRoot: got, Note: "root mismatch"}
	}
	return caseResult{ID: c.ID, Kind: c.Kind, Status: "PASS",
		ExpectedRoot: c.ExpectedRoot, ActualRoot: got}
}

// --- 辅助函数 ---

func sentinelToFloat(name string) float32 {
	switch name {
	case "NaN":
		return float32(math.NaN())
	case "+Inf":
		return float32(math.Inf(1))
	case "-Inf":
		return float32(math.Inf(-1))
	default:
		return 0
	}
}

func errorCode(err error) string {
	if err == nil {
		return ""
	}
	if err == canonical.ErrNonFinite {
		return "NON_FINITE_FEATURE"
	}
	return err.Error()
}

func fail(c manifestCase, format string, args ...interface{}) caseResult {
	return caseResult{ID: c.ID, Kind: c.Kind, Status: "FAIL",
		Note: fmt.Sprintf(format, args...)}
}

func sha256hex(b []byte) string {
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func die(format string, args ...interface{}) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(1)
}

func readManifest(path string) (*manifest, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var m manifest
	return &m, json.Unmarshal(raw, &m)
}

func writeJSON(path string, v interface{}) {
	os.MkdirAll(filepath.Dir(path), 0o755)
	data, _ := json.MarshalIndent(v, "", "  ")
	os.WriteFile(path, data, 0o644)
}
