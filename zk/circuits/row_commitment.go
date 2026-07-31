package circuits

import (
	"encoding/json"
	"fmt"
	"math/big"
	"os"
	"path/filepath"

	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	"github.com/consensys/gnark/frontend"
)

// RowCommitmentCircuit proves that a row's 18 packed field elements, together
// with the schema hash and row index, hash (under the pinned Poseidon2 width-4
// sponge H_P) to a publicly committed leaf. The Poseidon2 permutation is
// implemented in-circuit from the pinned gnark-crypto constants, so gnark is a
// genuine fourth independent implementation alongside Python/Go/Rust.
type RowCommitmentCircuit struct {
	Index     frontend.Variable `json:"index"`
	Packed    [18]frontend.Variable
	SchemaHi  frontend.Variable `gnark:",public"`
	SchemaLo  frontend.Variable `gnark:",public"`
	TagRow    frontend.Variable
	Expected  frontend.Variable `gnark:",public"`

	// Pinned constants (round keys + diagonal) injected as witnesses so the
	// circuit does not hardcode them. The prover supplies the canonical params.
	Diag      [4]frontend.Variable
	RoundKeys [64][4]frontend.Variable
}

// Define wires up the in-circuit Poseidon2 sponge and asserts the leaf.
func (c *RowCommitmentCircuit) Define(api frontend.API) error {
	// message = [tag, arity=21, schemaHi, schemaLo, index, packed...]
	msg := make([]frontend.Variable, 0, 2+3+18)
	msg = append(msg, c.TagRow, 21)
	msg = append(msg, c.SchemaHi, c.SchemaLo, c.Index)
	msg = append(msg, c.Packed[:]...)

	leaf := hpSponge(api, msg, c.Diag, c.RoundKeys)
	api.AssertIsEqual(leaf, c.Expected)
	return nil
}

// hpSponge is the in-circuit H_P: rate-3 sponge over the width-4 permutation.
func hpSponge(api frontend.API, msg []frontend.Variable, diag [4]frontend.Variable, rk [64][4]frontend.Variable) frontend.Variable {
	var state [4]frontend.Variable
	for i := 0; i < 4; i++ {
		state[i] = 0
	}
	idx := 0
	for idx < len(msg) {
		end := idx + 3
		if end > len(msg) {
			end = len(msg)
		}
		for j := idx; j < end; j++ {
			state[j-idx] = api.Add(state[j-idx], msg[j])
		}
		state = permuteCircuit(api, state, diag, rk)
		idx += 3
	}
	return state[0]
}

// permuteCircuit is the width-4 Poseidon2 permutation in-circuit (d=5, 8 full +
// 56 partial rounds), mirroring gnark-crypto exactly.
func permuteCircuit(api frontend.API, s [4]frontend.Variable, diag [4]frontend.Variable, rk [64][4]frontend.Variable) [4]frontend.Variable {
	const hf = 4
	const partial = 56
	s = externalCircuit(api, s)
	// first 4 full rounds
	for i := 0; i < hf; i++ {
		s = addRoundKeyCircuit(api, s, rk[i])
		for j := 0; j < 4; j++ {
			s[j] = sboxCircuit(api, s[j])
		}
		s = externalCircuit(api, s)
	}
	// 56 partial rounds
	for i := hf; i < hf+partial; i++ {
		s[0] = api.Add(s[0], rk[i][0])
		s[0] = sboxCircuit(api, s[0])
		s = internalCircuit(api, s, diag)
	}
	// last 4 full rounds
	for i := hf + partial; i < 2*hf+partial; i++ {
		s = addRoundKeyCircuit(api, s, rk[i])
		for j := 0; j < 4; j++ {
			s[j] = sboxCircuit(api, s[j])
		}
		s = externalCircuit(api, s)
	}
	return s
}

func sboxCircuit(api frontend.API, x frontend.Variable) frontend.Variable {
	x2 := api.Mul(x, x)
	x4 := api.Mul(x2, x2)
	return api.Mul(x4, x) // x^5
}

func externalCircuit(api frontend.API, s [4]frontend.Variable) [4]frontend.Variable {
	// M4 matrix (linear: only adds/doubles, no general mul).
	t0 := api.Add(s[0], s[1])
	t1 := api.Add(s[2], s[3])
	two_s1 := api.Add(s[1], s[1])
	two_s3 := api.Add(s[3], s[3])
	t2 := api.Add(t1, two_s1)
	t3 := api.Add(t0, two_s3)
	four_t1 := api.Add(api.Add(t1, t1), api.Add(t1, t1))
	four_t0 := api.Add(api.Add(t0, t0), api.Add(t0, t0))
	t4 := api.Add(four_t1, t3)
	t5 := api.Add(four_t0, t2)
	return [4]frontend.Variable{api.Add(t3, t5), t5, api.Add(t2, t4), t4}
}

func internalCircuit(api frontend.API, s [4]frontend.Variable, diag [4]frontend.Variable) [4]frontend.Variable {
	tot := api.Add(api.Add(s[0], s[1]), api.Add(s[2], s[3]))
	var out [4]frontend.Variable
	for i := 0; i < 4; i++ {
		term := api.Mul(s[i], diag[i])
		out[i] = api.Add(term, tot)
	}
	return out
}

func addRoundKeyCircuit(api frontend.API, s [4]frontend.Variable, rk [4]frontend.Variable) [4]frontend.Variable {
	for i := 0; i < 4; i++ {
		s[i] = api.Add(s[i], rk[i])
	}
	return s
}

// PoseidonConstants holds the pinned constants parsed from the spec file, used
// to build circuit witnesses.
type PoseidonConstants struct {
	Diag      [4]*big.Int
	RoundKeys [64][4]*big.Int
	Modulus   *big.Int
}

// LoadPoseidonConstants reads the pinned params JSON relative to the repo root.
func LoadPoseidonConstants() (*PoseidonConstants, error) {
	path := findSpecFile("poseidon2-bn254-v1.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var v struct {
		Modulus   string     `json:"modulus"`
		DiagM1    []string   `json:"diag_m1"`
		RoundKeys [][]string `json:"round_keys"`
	}
	if err := json.Unmarshal(raw, &v); err != nil {
		return nil, err
	}
	if len(v.DiagM1) != 4 || len(v.RoundKeys) != 64 {
		return nil, fmt.Errorf("unexpected param shape: diag=%d rounds=%d", len(v.DiagM1), len(v.RoundKeys))
	}
	pc := &PoseidonConstants{Modulus: mustParseHex(v.Modulus)}
	for i := 0; i < 4; i++ {
		pc.Diag[i] = mustParseHex(v.DiagM1[i])
	}
	for i := 0; i < 64; i++ {
		for j := 0; j < 4; j++ {
			pc.RoundKeys[i][j] = mustParseHex(v.RoundKeys[i][j])
		}
	}
	return pc, nil
}

// FeToBig converts a fr.Element to a canonical big.Int.
func FeToBig(e fr.Element) *big.Int { return e.BigInt(new(big.Int)) }

func mustParseHex(s string) *big.Int {
	v, ok := new(big.Int).SetString(s, 0)
	if !ok {
		panic("bad hex " + s)
	}
	return v
}

func findSpecFile(name string) string {
	dir, _ := os.Getwd()
	for i := 0; i < 8; i++ {
		c := filepath.Join(dir, "specs", name)
		if _, err := os.Stat(c); err == nil {
			return c
		}
		p := filepath.Dir(dir)
		if p == dir {
			break
		}
		dir = p
	}
	return filepath.Join("specs", name)
}
