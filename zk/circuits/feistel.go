package circuits

import "github.com/consensys/gnark/frontend"

func lowBits(api frontend.API, value frontend.Variable, count int) frontend.Variable {
	bits := api.ToBinary(value, 254)
	return api.FromBinary(bits[:count]...)
}

func xorWords(api frontend.API, a, b frontend.Variable, bits int) frontend.Variable {
	ab := api.ToBinary(a, bits)
	bb := api.ToBinary(b, bits)
	out := make([]frontend.Variable, bits)
	for i := 0; i < bits; i++ {
		out[i] = api.Xor(ab[i], bb[i])
	}
	return api.FromBinary(out...)
}

// Feistel17 is a four-round unbalanced Feistel permutation over [0,2^17).
// Initial halves are L:8 bits and R:9 bits. Even rounds output 8 bits;
// odd rounds output 9 bits, returning to the original split after 4 rounds.
func Feistel17(api frontend.API, seed, ordinal frontend.Variable) (frontend.Variable, error) {
	bits := api.ToBinary(ordinal, 17)
	l := api.FromBinary(bits[9:]...) // 8 bits
	r := api.FromBinary(bits[:9]...) // 9 bits

	for round := 0; round < 4; round++ {
		digest, err := Hash(api, TagFeistel, seed, round, r)
		if err != nil {
			return nil, err
		}
		if round%2 == 0 {
			f := lowBits(api, digest, 8)
			l, r = r, xorWords(api, l, f, 8) // now 9,8
		} else {
			f := lowBits(api, digest, 9)
			l, r = r, xorWords(api, l, f, 9) // now 8,9
		}
	}
	return api.Add(api.Mul(l, 512), r), nil
}
