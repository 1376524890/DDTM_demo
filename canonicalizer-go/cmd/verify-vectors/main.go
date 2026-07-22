package main

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

type TestCase struct {
	Name       string `json:"name"`
	RowCount   int    `json:"row_count"`
	BlobSize   int    `json:"blob_size"`
	BlobSHA256 string `json:"blob_sha256"`
}

type VectorsFile struct {
	Version   int        `json:"version"`
	TestCases []TestCase `json:"test_cases"`
}

type GoRow struct {
	Version   uint16
	RowID     uint64
	Valid     uint8
	Label     int8
	Timestamp uint64
	Mask      [16]byte
	Features  [128]int32
}

func unmarshalRow(data []byte) (*GoRow, error) {
	if len(data) < 548 {
		return nil, fmt.Errorf("row too short: %d bytes", len(data))
	}
	r := &GoRow{}
	off := 0
	r.Version = binary.LittleEndian.Uint16(data[off:]); off += 2
	r.RowID = binary.LittleEndian.Uint64(data[off:]); off += 8
	r.Valid = data[off]; off++
	r.Label = int8(data[off]); off++
	r.Timestamp = binary.LittleEndian.Uint64(data[off:]); off += 8
	copy(r.Mask[:], data[off:off+16]); off += 16
	for i := 0; i < 128; i++ {
		r.Features[i] = int32(binary.LittleEndian.Uint32(data[off:])); off += 4
	}
	return r, nil
}

func sha256hex(data []byte) string {
	h := sha256.Sum256(data)
	return hex.EncodeToString(h[:])
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "Usage: verify-vectors <vectors.json>\n")
		os.Exit(1)
	}

	jsonPath := os.Args[1]
	binDir := filepath.Dir(jsonPath)

	data, err := os.ReadFile(jsonPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	var vf VectorsFile
	if err := json.Unmarshal(data, &vf); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	passed := 0
	failed := 0
	rowsOk := 0
	rowsBad := 0

	for _, tc := range vf.TestCases {
		fmt.Printf("=== %s (%d rows) ===\n", tc.Name, tc.RowCount)

		binPath := filepath.Join(binDir, tc.Name+".bin")
		blob, err := os.ReadFile(binPath)
		if err != nil {
			fmt.Printf("  FAIL: cannot read %s: %v\n", binPath, err)
			failed++
			continue
		}

		// Size check
		if len(blob) != tc.BlobSize {
			fmt.Printf("  FAIL: blob size mismatch: %d vs %d\n", len(blob), tc.BlobSize)
			failed++
			continue
		}

		// SHA-256 check
		if got := sha256hex(blob); got != tc.BlobSHA256 {
			fmt.Printf("  FAIL: SHA-256 mismatch\n  expected: %s\n  got:      %s\n",
				tc.BlobSHA256, got)
			failed++
			continue
		}

		// Row count check
		rowCount := len(blob) / 548
		if rowCount != tc.RowCount {
			fmt.Printf("  FAIL: row count mismatch: %d vs %d\n", rowCount, tc.RowCount)
			failed++
			continue
		}

		// Structural scan
		bad := 0
		for i := 0; i < rowCount; i++ {
			_, err := unmarshalRow(blob[i*548 : (i+1)*548])
			if err != nil {
				if bad < 3 {
					fmt.Printf("  FAIL: row %d: %v\n", i, err)
				}
				bad++
			}
		}
		if bad > 0 {
			fmt.Printf("  FAIL: %d/%d rows unmarshal errors\n", bad, rowCount)
			failed++
			rowsBad += bad
		} else {
			fmt.Printf("  PASS: all %d rows valid\n", rowCount)
			passed++
			rowsOk += rowCount
		}
	}

	fmt.Printf("\n========================================\n")
	fmt.Printf("Cases: %d passed, %d failed\n", passed, failed)
	fmt.Printf("Rows:  %d ok, %d bad\n", rowsOk, rowsBad)
	if failed > 0 {
		os.Exit(1)
	}
}
