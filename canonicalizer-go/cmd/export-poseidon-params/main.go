// Command export-poseidon-params dumps the exact BN254 Poseidon2 width-4
// parameters used by gnark-crypto v0.20.1, together with known-answer-test
// (KAT) vectors. The output JSON is the single source of truth consumed by
// the Python and Rust reference implementations, so that every language runs
// the identical permutation and therefore the identical Merkle root.
//
// We deliberately pin width=4. gnark-crypto only hard-codes audited
// constants for t in {4,8,12,16}; t=2,3 are derived at runtime via Keccak and
// would force every reimplementation to reproduce gnark-crypto's Keccak-based
// key schedule. Width 4 uses the hardcoded, audited constants and is the
// smallest such width, minimising the constant surface that must be kept in
// sync across languages.
package main

import (
	"encoding/json"
	"fmt"
	"math/big"
	"os"

	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	"github.com/consensys/gnark-crypto/ecc/bn254/fr/poseidon2"
)

// ParamFile is the on-disk representation of the frozen Poseidon2 instance.
type ParamFile struct {
	Protocol       string     `json:"protocol"`
	Version        int        `json:"version"`
	Field          string     `json:"field"`
	Modulus        string     `json:"modulus"`
	Width          int        `json:"width"`
	FullRounds     int        `json:"full_rounds"`
	PartialRounds  int        `json:"partial_rounds"`
	SBoxDegree     int        `json:"sbox_degree"`
	DiagM1         []string   `json:"diag_m1"`
	RoundKeys      [][]string `json:"round_keys"`
	RoundKeyWidths []int      `json:"round_key_widths"`
	KAT            []KAT      `json:"kat"`
	ParameterSource string    `json:"parameter_source"`
}

// KAT is a single known-answer-test vector for the permutation.
type KAT struct {
	Input  []string `json:"input"`
	Output []string `json:"output"`
}

// elementHex renders an fr.Element as a 0x-prefixed big-endian canonical
// integer string (matching fr.Element.Bytes() ordering).
func elementHex(e fr.Element) string {
	b := e.Bytes()
	return "0x" + new(big.Int).SetBytes(b[:]).Text(16)
}

func katFor(input []string) KAT {
	width := len(input)
	buf := make([]fr.Element, width)
	for i, s := range input {
		v, ok := new(big.Int).SetString(s, 0)
		if !ok {
			panic("bad input " + s)
		}
		buf[i].SetBigInt(v)
	}
	perm := poseidon2.NewPermutation(width, 8, 56)
	if err := perm.Permutation(buf); err != nil {
		panic(err)
	}
	out := make([]string, width)
	for i := range buf {
		out[i] = elementHex(buf[i])
	}
	return KAT{Input: input, Output: out}
}

func main() {
	const width = 4
	// NewParameters returns the exported parameter struct (Width, RoundKeys,
	// DiagM1, ...). It reads the hardcoded audited constants for t=4.
	params := poseidon2.NewParameters(width, 8, 56)

	// BN254 scalar field modulus.
	modulus := fr.Modulus()

	out := ParamFile{
		Protocol:        "DDTM-POSEIDON2-BN254",
		Version:         1,
		Field:           "BN254 scalar field",
		Modulus:         "0x" + modulus.Text(16),
		Width:           width,
		FullRounds:      params.NbFullRounds,
		PartialRounds:   params.NbPartialRounds,
		SBoxDegree:      poseidon2.DegreeSBox(),
		DiagM1:          make([]string, len(params.DiagM1)),
		RoundKeys:       make([][]string, len(params.RoundKeys)),
		RoundKeyWidths:  make([]int, len(params.RoundKeys)),
		ParameterSource: "gnark-crypto v0.20.1 hardcoded BN254 width-4 constants",
	}

	for i, e := range params.DiagM1 {
		out.DiagM1[i] = elementHex(e)
	}
	for i, round := range params.RoundKeys {
		out.RoundKeyWidths[i] = len(round)
		out.RoundKeys[i] = make([]string, len(round))
		for j, e := range round {
			out.RoundKeys[i][j] = elementHex(e)
		}
	}

	// KAT vectors: a spread of representative inputs. These let the Python
	// and Rust reimplementations prove they reproduce gnark-crypto exactly.
	out.KAT = []KAT{
		katFor([]string{"0x0", "0x0", "0x0", "0x0"}),
		katFor([]string{"0x1", "0x2", "0x3", "0x4"}),
		katFor([]string{"0xa", "0xb", "0xc", "0xd"}),
		katFor([]string{
			"0x123456789abcdef0123456789abcdef0",
			"0xfedcba9876543210fedcba9876543210",
			"0x1",
			"0x2",
		}),
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(&out); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
