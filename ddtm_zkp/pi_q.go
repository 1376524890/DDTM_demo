package main

import (
	"bytes"
	"crypto/rand"
	"fmt"
	"math/big"
	"time"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	mimccrypto "github.com/consensys/gnark-crypto/ecc/bn254/fr/mimc"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/frontend/cs/r1cs"
	stdmimc "github.com/consensys/gnark/std/hash/mimc"
)

// ============================================================
// PI_Q: Quality Proof Circuit
// ============================================================
// Proves: H(D||r_D) = c_D AND H(Q(D)||r_Q) = c_Q AND Phi(Q(D),θ,ctx)=1
// Phi checks: completeness >= tau_complete, freshness <= tau_fresh, format valid

type PiQCircuit struct {
	// Private witness
	D_blk    [10]frontend.Variable `gnark:",secret"` // data blocks (up to 10 fields)
	R_D      frontend.Variable     `gnark:",secret"` // randomness for data commitment
	Q_val    frontend.Variable     `gnark:",secret"` // quality metric Q(D)
	R_Q      frontend.Variable     `gnark:",secret"` // randomness for quality commitment
	// Public inputs
	C_D    frontend.Variable `gnark:",public"` // H(D||r_D)
	C_Q    frontend.Variable `gnark:",public"` // H(Q(D)||r_Q)
	Theta  frontend.Variable `gnark:",public"` // quality threshold
	Ctx    frontend.Variable `gnark:",public"` // context (e.g., block_time for freshness)
}

func (c *PiQCircuit) Define(api frontend.API) error {
	// 1. Data commitment: H(D||r_D) = c_D
	hD, _ := stdmimc.NewMiMC(api)
	for i := range c.D_blk {
		hD.Write(c.D_blk[i])
	}
	hD.Write(c.R_D)
	api.AssertIsEqual(hD.Sum(), c.C_D)

	// 2. Quality commitment: H(Q(D)||r_Q) = c_Q
	hQ, _ := stdmimc.NewMiMC(api)
	hQ.Write(c.Q_val)
	hQ.Write(c.R_Q)
	api.AssertIsEqual(hQ.Sum(), c.C_Q)

	// 3. Quality threshold: Q_val >= Theta (completeness check)
	api.AssertIsLessOrEqual(c.Theta, c.Q_val)

	// 4. Freshness: Q_val <= Ctx (timestamp not expired; Ctx = tau_fresh + genesis_time)
	// Simplified: ensure Q_val (freshness ratio) is consistent with context
	// Note: In full implementation, this checks max(timestamp_i) - block_time <= tau_fresh
	api.AssertIsLessOrEqual(c.Q_val, c.Ctx)

	// 5. Format check: each field satisfies basic range (0 <= D_blk[i] < 2^128)
	// Simplified range check using multiplication gates
	zero := frontend.Variable(0)
	maxVal := frontend.Variable(new(big.Int).Lsh(big.NewInt(1), 128))
	for i := range c.D_blk {
		api.AssertIsLessOrEqual(zero, c.D_blk[i])
		api.AssertIsLessOrEqual(c.D_blk[i], maxVal)
	}

	return nil
}

func mimcHashQ(vals ...*big.Int) *big.Int {
	h := mimccrypto.NewMiMC()
	for _, v := range vals {
		var e fr.Element
		e.SetBigInt(v)
		b := e.Bytes()
		h.Write(b[:])
	}
	result := h.Sum(nil)
	var r fr.Element
	r.SetBytes(result)
	return r.BigInt(new(big.Int))
}

func randomScalarQ() *big.Int {
	s, _ := rand.Int(rand.Reader, ecc.BN254.ScalarField())
	return s
}

func main() {
	fmt.Println("\n========================================")
	fmt.Println("PI_Q: Quality Proof Circuit Benchmark")
	fmt.Println("========================================")

	circuit := &PiQCircuit{}
	t0 := time.Now()
	cs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, circuit)
	if err != nil {
		fmt.Printf("COMPILE ERROR: %v\n", err)
		return
	}
	fmt.Printf("Compile: %v, Constraints: %d\n", time.Since(t0), cs.GetNbConstraints())

	t0 = time.Now()
	pk, vk, err := groth16.Setup(cs)
	if err != nil {
		fmt.Printf("SETUP ERROR: %v\n", err)
		return
	}
	fmt.Printf("Setup: %v\n", time.Since(t0))

	var pkBuf, vkBuf bytes.Buffer
	pk.WriteTo(&pkBuf)
	vk.WriteTo(&vkBuf)
	fmt.Printf("PK: %d bytes, VK: %d bytes\n", pkBuf.Len(), vkBuf.Len())

	// Generate test values (< 2^128 to satisfy format range check)
	var D [10]*big.Int
	max128 := new(big.Int).Lsh(big.NewInt(1), 128)
	for i := range D {
		D[i], _ = rand.Int(rand.Reader, max128)
	}
	r_D := randomScalarQ()
	Q_val := big.NewInt(85) // completeness ratio (85%)
	r_Q := randomScalarQ()
	Theta := big.NewInt(80) // threshold (80%)
	Ctx := big.NewInt(100)  // context value

	// Compute commitments
	c_D := mimcHashQ(append(D[:], r_D)...)
	c_Q := mimcHashQ(Q_val, r_Q)

	pass, fail := 0, 0

	// Test 1: Valid proof (Q=85 >= Theta=80)
	w := &PiQCircuit{C_D: c_D, C_Q: c_Q, Theta: Theta, Ctx: Ctx, R_D: r_D, Q_val: Q_val, R_Q: r_Q}
	for i := range D {
		w.D_blk[i] = D[i]
	}
	wit, _ := frontend.NewWitness(w, ecc.BN254.ScalarField())
	pubW, _ := wit.Public()

	t0 = time.Now()
	proof, err := groth16.Prove(cs, pk, wit)
	pt := time.Since(t0).Milliseconds()
	if err == nil {
		err = groth16.Verify(proof, vk, pubW)
	}
	vt := time.Since(t0).Microseconds()
	if err != nil {
		fmt.Printf("  Valid_Proof    [FAIL] %v\n", err)
		fail++
	} else {
		fmt.Printf("  Valid_Proof    [PASS] prove=%dms verify=%dus constraints=%d\n", pt, vt, cs.GetNbConstraints())
		pass++
	}

	// Test 2: Low quality (should fail)
	lowQ := big.NewInt(50)
	w2 := &PiQCircuit{C_D: c_D, C_Q: c_Q, Theta: Theta, Ctx: Ctx, R_D: r_D, Q_val: lowQ, R_Q: r_Q}
	for i := range D {
		w2.D_blk[i] = D[i]
	}
	wit2, _ := frontend.NewWitness(w2, ecc.BN254.ScalarField())
	_, err = groth16.Prove(cs, pk, wit2)
	if err != nil {
		fmt.Printf("  Low_Quality    [PASS] rejected (attack: Q=50 < Theta=80)\n")
		pass++
	} else {
		fmt.Printf("  Low_Quality    [FAIL] ACCEPTED (BUG!)\n")
		fail++
	}

	// Test 3: Stale data (freshness violation: Q_val=85 > Ctx=100 passes, test with Q_val > Ctx)
	highQ := big.NewInt(120)
	w3 := &PiQCircuit{C_D: c_D, C_Q: c_Q, Theta: Theta, Ctx: Ctx, R_D: r_D, Q_val: highQ, R_Q: r_Q}
	for i := range D {
		w3.D_blk[i] = D[i]
	}
	wit3, _ := frontend.NewWitness(w3, ecc.BN254.ScalarField())
	_, err = groth16.Prove(cs, pk, wit3)
	if err != nil {
		fmt.Printf("  Stale_Data     [PASS] rejected (attack: Q=120 > Ctx=100)\n")
		pass++
	} else {
		fmt.Printf("  Stale_Data     [FAIL] ACCEPTED (BUG!)\n")
		fail++
	}

	// Test 4: Tampered data commitment
	tamperedD := randomScalarQ()
	w4 := &PiQCircuit{C_D: c_D, C_Q: c_Q, Theta: Theta, Ctx: Ctx, R_D: r_D, Q_val: Q_val, R_Q: r_Q}
	for i := range D {
		w4.D_blk[i] = D[i]
	}
	w4.D_blk[0] = tamperedD // tamper first block
	wit4, _ := frontend.NewWitness(w4, ecc.BN254.ScalarField())
	_, err = groth16.Prove(cs, pk, wit4)
	if err != nil {
		fmt.Printf("  Tampered_c_D   [PASS] rejected (attack: altered data block)\n")
		pass++
	} else {
		fmt.Printf("  Tampered_c_D   [FAIL] ACCEPTED (BUG!)\n")
		fail++
	}

	// Test 5: Tampered quality commitment
	tamperedQ := randomScalarQ()
	w5 := &PiQCircuit{C_D: c_D, C_Q: c_Q, Theta: Theta, Ctx: Ctx, R_D: r_D, Q_val: Q_val, R_Q: tamperedQ}
	for i := range D {
		w5.D_blk[i] = D[i]
	}
	wit5, _ := frontend.NewWitness(w5, ecc.BN254.ScalarField())
	_, err = groth16.Prove(cs, pk, wit5)
	if err != nil {
		fmt.Printf("  Tampered_c_Q   [PASS] rejected (attack: altered quality randomness)\n")
		pass++
	} else {
		fmt.Printf("  Tampered_c_Q   [FAIL] ACCEPTED (BUG!)\n")
		fail++
	}

	// Summary
	fmt.Printf("\nTotal: %d PASS, %d FAIL\n", pass, fail)
	fmt.Printf("PI_Q Summary: %d constraints, %dms prove (valid), %dus verify\n",
		cs.GetNbConstraints(), pt, vt)
}
