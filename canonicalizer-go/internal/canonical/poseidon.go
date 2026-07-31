// Package canonical implements the DDTM-CANONICAL-V1 deterministic data layer
// in Go: IEEE-754→Q16.16 quantization, the 548-byte row codec, the BN254
// Poseidon2 width-4 permutation (constants pinned to gnark-crypto v0.20.1),
// the domain-tagged sponge H_P, and the Merkle tree.
//
// The permutation is written from scratch (independent round structure) but
// performs field arithmetic with gnark-crypto's fr.Element — the native BN254
// scalar-field type — so it is fast yet provably identical to gnark-crypto.
// The bundled KAT vectors are re-derived at load time and abort on any mismatch.
package canonical

import (
	"encoding/json"
	"fmt"
	"math/big"
	"os"
	"path/filepath"

	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
)

// poseidonParams mirrors specs/poseidon2-bn254-v1.json.
type poseidonParams struct {
	Modulus       string     `json:"modulus"`
	Width         int        `json:"width"`
	FullRounds    int        `json:"full_rounds"`
	PartialRounds int        `json:"partial_rounds"`
	DiagM1        []string   `json:"diag_m1"`
	RoundKeys     [][]string `json:"round_keys"`
	KAT           []struct {
		Input  []string `json:"input"`
		Output []string `json:"output"`
	} `json:"kat"`
}

// Poseidon holds the pinned BN254 Poseidon2 width-4 instance.
type Poseidon struct {
	P             *big.Int // modulus, for reference / output formatting only
	Diag          [4]fr.Element
	RoundKeys     [][4]fr.Element
	Width         int
	FullRounds    int
	PartialRounds int
	halfFull      int
}

var sharedPoseidon *Poseidon

// LoadPoseidon reads the pinned parameter file and self-checks via the KAT.
func LoadPoseidon(specPath string) (*Poseidon, error) {
	if specPath == "" {
		specPath = findSpec("poseidon2-bn254-v1.json")
	}
	raw, err := os.ReadFile(specPath)
	if err != nil {
		return nil, fmt.Errorf("read poseidon params: %w", err)
	}
	var p poseidonParams
	if err := json.Unmarshal(raw, &p); err != nil {
		return nil, fmt.Errorf("parse poseidon params: %w", err)
	}

	inst := &Poseidon{
		P:             mustHex(p.Modulus),
		Width:         p.Width,
		FullRounds:    p.FullRounds,
		PartialRounds: p.PartialRounds,
		halfFull:      p.FullRounds / 2,
	}
	for i, h := range p.DiagM1 {
		inst.Diag[i].SetBigInt(mustHex(h))
	}
	inst.RoundKeys = make([][4]fr.Element, len(p.RoundKeys))
	for i, rnd := range p.RoundKeys {
		for j, h := range rnd {
			inst.RoundKeys[i][j].SetBigInt(mustHex(h))
		}
	}

	// Self-check: our permutation must reproduce every gnark-crypto KAT.
	for _, kat := range p.KAT {
		var in [4]fr.Element
		for i, h := range kat.Input {
			in[i].SetBigInt(mustHex(h))
		}
		got := inst.Permute(in)
		for i := range got {
			expBI := mustHex(kat.Output[i])
			gotBI := got[i].BigInt(new(big.Int))
			if gotBI.Cmp(expBI) != 0 {
				return nil, fmt.Errorf("poseidon KAT mismatch on input %v", kat.Input)
			}
		}
	}
	sharedPoseidon = inst
	return inst, nil
}

// SharedPoseidon returns the last-loaded instance.
func SharedPoseidon() *Poseidon { return sharedPoseidon }

// Permute applies the width-4 Poseidon2 permutation. Mirrors gnark-crypto
// exactly (verified by the KAT self-check).
func (p *Poseidon) Permute(state [4]fr.Element) [4]fr.Element {
	s := state

	external := func() {
		var t0, t1, t2, t3, t4, t5, tmp fr.Element
		t0.Add(&s[0], &s[1])
		t1.Add(&s[2], &s[3])
		tmp.Double(&s[1])      // 2*s1
		t2.Add(&t1, &tmp)      // t1 + 2*s1
		tmp.Double(&s[3])      // 2*s3
		t3.Add(&t0, &tmp)      // t0 + 2*s3
		tmp.Double(&t1).Double(&tmp) // 4*t1
		t4.Add(&tmp, &t3)      // 4*t1 + t3
		tmp.Double(&t0).Double(&tmp) // 4*t0
		t5.Add(&tmp, &t2)      // 4*t0 + t2
		s[0].Add(&t3, &t5)
		s[1].Set(&t5)
		s[2].Add(&t2, &t4)
		s[3].Set(&t4)
	}
	sbox := func(i int) {
		var x2, x4 fr.Element
		x2.Square(&s[i])
		x4.Square(&x2)
		s[i].Mul(&x4, &s[i]) // x^5
	}

	external()

	hf := p.halfFull
	// first half full rounds
	for i := 0; i < hf; i++ {
		rk := &p.RoundKeys[i]
		for j := 0; j < 4; j++ {
			s[j].Add(&s[j], &rk[j])
		}
		for j := 0; j < 4; j++ {
			sbox(j)
		}
		external()
	}
	// partial rounds
	for i := hf; i < hf+p.PartialRounds; i++ {
		s[0].Add(&s[0], &p.RoundKeys[i][0])
		sbox(0)
		var tot fr.Element
		tot.Add(&s[0], &s[1]).Add(&tot, &s[2]).Add(&tot, &s[3])
		for j := 0; j < 4; j++ {
			var term fr.Element
			term.Mul(&s[j], &p.Diag[j])
			s[j].Add(&term, &tot)
		}
	}
	// second half full rounds
	for i := hf + p.PartialRounds; i < p.FullRounds+p.PartialRounds; i++ {
		rk := &p.RoundKeys[i]
		for j := 0; j < 4; j++ {
			s[j].Add(&s[j], &rk[j])
		}
		for j := 0; j < 4; j++ {
			sbox(j)
		}
		external()
	}
	return s
}

// HashPoseidon is H_P(tag, elements): absorb [tag, arity, elements...] through
// a rate-3 sponge over the width-4 permutation and squeeze element 0.
func (p *Poseidon) HashPoseidon(tag fr.Element, elements []fr.Element) fr.Element {
	msg := make([]fr.Element, 0, 2+len(elements))
	var arity fr.Element
	arity.SetUint64(uint64(len(elements)))
	msg = append(msg, tag, arity)
	msg = append(msg, elements...)

	var state [4]fr.Element // zero state
	for idx := 0; idx < len(msg); idx += 3 {
		end := idx + 3
		if end > len(msg) {
			end = len(msg)
		}
		for j := idx; j < end; j++ {
			state[j-idx].Add(&state[j-idx], &msg[j])
		}
		state = p.Permute(state)
	}
	return state[0]
}

func mustHex(s string) *big.Int {
	v, ok := new(big.Int).SetString(s, 0)
	if !ok {
		panic("bad hex: " + s)
	}
	return v
}

// findSpec locates a specs/ file by walking up from the current directory.
func findSpec(name string) string {
	dir, _ := os.Getwd()
	for i := 0; i < 8; i++ {
		candidate := filepath.Join(dir, "specs", name)
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return filepath.Join("specs", name)
}
