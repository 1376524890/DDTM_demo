package circuits

import (
	"fmt"
	"math/big"

	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	"github.com/consensys/gnark-crypto/ecc/bn254/fr/poseidon2"
)

// NativeFeistel17 computes the 4-round unbalanced Feistel permutation
// over the 17-bit input space. It is only used for witness generation,
// never inside the circuit.
func NativeFeistel17(seed, ordinal *big.Int) *big.Int {
	if ordinal.BitLen() > 17 {
		panic("ordinal exceeds 17 bits")
	}
	x := new(big.Int).Set(ordinal)
	l := new(big.Int).Rsh(x, 9)               // bits 9..16 (8 bits)
	r := new(big.Int).And(x, new(big.Int).SetUint64(511)) // bits 0..8 (9 bits)

	for round := 0; round < 4; round++ {
		h := nativeHash(TagFeistelBig(), seed, big.NewInt(int64(round)), r)
		if round%2 == 0 {
			f := new(big.Int).And(h, new(big.Int).SetUint64(255)) // 8 bits
			l.Xor(l, f)
			l.And(l, new(big.Int).SetUint64(255))
		} else {
			f := new(big.Int).And(h, new(big.Int).SetUint64(511)) // 9 bits
			l.Xor(l, f)
			l.And(l, new(big.Int).SetUint64(511))
		}
		l, r = r, l
	}

	result := new(big.Int).Lsh(l, 9)
	result.Or(result, r)
	return result
}

var tagFeistelBig = new(big.Int).SetUint64(0x44465001)

func TagFeistelBig() *big.Int { return new(big.Int).Set(tagFeistelBig) }

func nativeHash(values ...*big.Int) *big.Int {
	h := poseidon2.NewMerkleDamgardHasher()
	for _, v := range values {
		if v.Sign() < 0 {
			panic("negative field input in native hash")
		}
		var e fr.Element
		e.SetBigInt(v)
		b := e.Bytes()
		if _, err := h.Write(b[:]); err != nil {
			panic(fmt.Sprintf("native hash write: %v", err))
		}
	}
	digest := h.Sum(nil)
	var out fr.Element
	if err := out.SetBytesCanonical(digest); err != nil {
		panic(fmt.Sprintf("native hash finalize: %v", err))
	}
	return out.BigInt(new(big.Int))
}

// NativeInverseFeistel17 computes the inverse of the 4-round unbalanced
// Feistel permutation. For any valid (seed, ordinal):
//
//	NativeInverseFeistel17(seed, NativeFeistel17(seed, ordinal)) == ordinal
func NativeInverseFeistel17(seed, value *big.Int) *big.Int {
	if value.BitLen() > 17 {
		panic("value exceeds 17 bits")
	}
	// Decode: L is upper 8 bits, R is lower 9 bits.
	l := new(big.Int).Rsh(value, 9)        // bits 9..16 (8 bits)
	r := new(big.Int).And(value, new(big.Int).SetUint64(511)) // bits 0..8 (9 bits)

	// Run rounds in reverse: 3, 2, 1, 0.
	// Forward round was: l = l XOR f(r), then swap(l, r).
	// Inverse round is:   unswap, then l = l XOR f(r).
	for round := 3; round >= 0; round-- {
		// Undo the swap that happened at the end of the forward round.
		l, r = r, l

		h := nativeHash(TagFeistelBig(), seed, big.NewInt(int64(round)), r)
		if round%2 == 0 {
			f := new(big.Int).And(h, new(big.Int).SetUint64(255)) // 8 bits
			l.Xor(l, f)
			l.And(l, new(big.Int).SetUint64(255))
		} else {
			f := new(big.Int).And(h, new(big.Int).SetUint64(511)) // 9 bits
			l.Xor(l, f)
			l.And(l, new(big.Int).SetUint64(511))
		}
	}

	result := new(big.Int).Lsh(l, 9)
	result.Or(result, r)
	return result
}

// NativeCycleWalk finds the valid audit index by re-applying Feistel17
// until the result is < rowCount.
func NativeCycleWalk(seed *big.Int, ordinal uint64, rowCount uint64) (uint64, int, error) {
	seedBig := new(big.Int).Set(seed)
	x := NativeFeistel17(seedBig, new(big.Int).SetUint64(ordinal))
	iters := 0
	for x.Cmp(new(big.Int).SetUint64(rowCount)) >= 0 {
		if iters >= MaxCycleWalkIterations {
			return 0, iters, fmt.Errorf("cycle-walk exceeded max iterations for N=%d", rowCount)
		}
		x = NativeFeistel17(seedBig, x)
		iters++
	}
	return x.Uint64(), iters, nil
}
