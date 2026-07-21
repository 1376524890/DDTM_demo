package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"math/big"
	"os"
	"strconv"

	"github.com/1376524890/ddtm-qas/canonicalizer/internal/codec"
	"github.com/1376524890/ddtm-qas/canonicalizer/internal/merkle"
)

type Manifest struct {
	Version         int    `json:"version"`
	RowCount        int    `json:"row_count"`
	TreeCapacity    int    `json:"tree_capacity"`
	FeatureCount    int    `json:"feature_count"`
	SchemaSHA256    string `json:"schema_sha256"`
	SchemaField     string `json:"schema_field"`
	DatasetVersion  string `json:"dataset_version"`
	DataRoot        string `json:"data_root"`
	CanonicalSHA256 string `json:"canonical_sha256"`
}

func scalarFromDigest(b [32]byte) *big.Int {
	n := new(big.Int).SetBytes(b[:])
	modulus, _ := new(big.Int).SetString("21888242871839275222246405745257275088548364400416034343698204186575808495617", 10)
	return n.Mod(n, modulus)
}

func main() {
	input := flag.String("input", "", "CSV: label,timestamp,f0..f127; empty feature means missing")
	schema := flag.String("schema", "", "canonical schema JSON")
	output := flag.String("output", "dataset.canonical.bin", "canonical binary output")
	manifestPath := flag.String("manifest", "dataset.manifest.json", "manifest output")
	datasetVersion := flag.Uint64("dataset-version", 1, "monotonic dataset version")
	flag.Parse()
	if *input == "" || *schema == "" {
		flag.Usage()
		os.Exit(2)
	}

	schemaBytes, err := os.ReadFile(*schema)
	must(err)
	schemaDigest := sha256.Sum256(schemaBytes)
	schemaField := scalarFromDigest(schemaDigest)
	versionField := new(big.Int).SetUint64(*datasetVersion)

	in, err := os.Open(*input)
	must(err)
	defer in.Close()
	out, err := os.Create(*output)
	must(err)
	defer out.Close()
	canonicalHash := sha256.New()
	writer := io.MultiWriter(out, canonicalHash)

	reader := csv.NewReader(bufio.NewReader(in))
	reader.ReuseRecord = true
	leaves := make([]*big.Int, merkle.TreeCapacity)
	rowCount := 0
	for {
		record, err := reader.Read()
		if err == io.EOF {
			break
		}
		must(err)
		if len(record) != 2+codec.FeatureCount {
			panic(fmt.Errorf("row %d: expected 130 columns, got %d", rowCount, len(record)))
		}
		if rowCount >= 100000 {
			panic("row count exceeds policy")
		}
		label64, err := strconv.ParseInt(record[0], 10, 8)
		must(err)
		ts, err := strconv.ParseUint(record[1], 10, 64)
		must(err)
		row := codec.Row{Version: codec.RowVersion, RowID: uint64(rowCount), Valid: 1, Label: int8(label64), Timestamp: ts}
		for i := 0; i < codec.FeatureCount; i++ {
			if record[i+2] == "" {
				row.MissingMask[i/8] |= byte(1 << uint(i%8))
				row.Features[i] = 0
				continue
			}
			q, err := strconv.ParseInt(record[i+2], 10, 32)
			must(err)
			row.Features[i] = int32(q)
		}
		raw, err := row.MarshalBinary()
		must(err)
		_, err = writer.Write(raw)
		must(err)
		leaf, err := merkle.Leaf(row, schemaField, versionField)
		must(err)
		leaves[rowCount] = leaf
		rowCount++
	}
	for i := rowCount; i < merkle.TreeCapacity; i++ {
		leaf, err := merkle.PaddingLeaf(uint64(i), schemaField, versionField)
		must(err)
		leaves[i] = leaf
	}
	tree, err := merkle.Build(leaves)
	must(err)
	man := Manifest{
		Version: 1, RowCount: rowCount, TreeCapacity: merkle.TreeCapacity,
		FeatureCount: codec.FeatureCount,
		SchemaSHA256: hex.EncodeToString(schemaDigest[:]), SchemaField: schemaField.String(),
		DatasetVersion: versionField.String(), DataRoot: tree.Root().String(),
		CanonicalSHA256: hex.EncodeToString(canonicalHash.Sum(nil)),
	}
	data, err := json.MarshalIndent(man, "", "  ")
	must(err)
	must(os.WriteFile(*manifestPath, data, 0o644))
	fmt.Printf("rows=%d root=%s\n", rowCount, tree.Root().String())
}

func must(err error) {
	if err != nil {
		panic(err)
	}
}
