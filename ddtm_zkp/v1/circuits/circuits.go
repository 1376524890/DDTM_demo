package circuits

import (
	"crypto/rand"
	"fmt"
	"math/big"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	mimccrypto "github.com/consensys/gnark-crypto/ecc/bn254/fr/mimc"
	"github.com/consensys/gnark/frontend"
	stdmimc "github.com/consensys/gnark/std/hash/mimc"
)

const (
	BlockCount       = 16
	RecordCount      = 4
	QualityPurpose   = 1
	KeyPurpose       = 2
	DeliveryPurpose  = 3
)

// Each record occupies four field elements: value, timestamp, present-bit, reserved-zero.
type QualityCircuit struct {
	Blocks [BlockCount]frontend.Variable `gnark:",secret"`
	RD     frontend.Variable             `gnark:",secret"`
	RQ     frontend.Variable             `gnark:",secret"`

	CD         frontend.Variable `gnark:",public"`
	CQ         frontend.Variable `gnark:",public"`
	MinPresent frontend.Variable `gnark:",public"`
	MaxValue   frontend.Variable `gnark:",public"`
	MaxAge     frontend.Variable `gnark:",public"`
	AsOfTime   frontend.Variable `gnark:",public"`
	Context    frontend.Variable `gnark:",public"`
	Binding    frontend.Variable `gnark:",public"`
}

func (c *QualityCircuit) Define(api frontend.API) error {
	hD, err := stdmimc.NewMiMC(api)
	if err != nil {
		return err
	}
	for i := range c.Blocks {
		hD.Write(c.Blocks[i])
	}
	hD.Write(c.RD)
	api.AssertIsEqual(hD.Sum(), c.CD)

	validCount := frontend.Variable(0)
	for i := 0; i < RecordCount; i++ {
		value := c.Blocks[i*4]
		timestamp := c.Blocks[i*4+1]
		present := c.Blocks[i*4+2]
		reserved := c.Blocks[i*4+3]

		api.AssertIsBoolean(present)
		api.AssertIsEqual(reserved, 0)
		api.AssertIsLessOrEqual(value, c.MaxValue)
		api.AssertIsLessOrEqual(timestamp, c.AsOfTime)
		api.AssertIsLessOrEqual(api.Sub(c.AsOfTime, timestamp), c.MaxAge)
		// Missing records must not carry a hidden non-zero value.
		api.AssertIsEqual(api.Mul(api.Sub(1, present), value), 0)
		validCount = api.Add(validCount, present)
	}
	api.AssertIsLessOrEqual(c.MinPresent, validCount)

	hQ, err := stdmimc.NewMiMC(api)
	if err != nil {
		return err
	}
	hQ.Write(validCount)
	hQ.Write(c.RQ)
	api.AssertIsEqual(hQ.Sum(), c.CQ)

	hBinding, err := stdmimc.NewMiMC(api)
	if err != nil {
		return err
	}
	hBinding.Write(c.CD)
	hBinding.Write(c.CQ)
	hBinding.Write(c.Context)
	hBinding.Write(QualityPurpose)
	api.AssertIsEqual(hBinding.Sum(), c.Binding)
	return nil
}

type KeyCircuit struct {
	Key  frontend.Variable `gnark:",secret"`
	RK   frontend.Variable `gnark:",secret"`
	REnc frontend.Variable `gnark:",secret"`

	CK       frontend.Variable `gnark:",public"`
	BuyerKey frontend.Variable `gnark:",public"`
	KEnc     frontend.Variable `gnark:",public"`
	Context  frontend.Variable `gnark:",public"`
	Binding  frontend.Variable `gnark:",public"`
}

func (c *KeyCircuit) Define(api frontend.API) error {
	hK, err := stdmimc.NewMiMC(api)
	if err != nil {
		return err
	}
	hK.Write(c.Key)
	hK.Write(c.RK)
	api.AssertIsEqual(hK.Sum(), c.CK)

	hEnvelope, err := stdmimc.NewMiMC(api)
	if err != nil {
		return err
	}
	hEnvelope.Write(c.BuyerKey)
	hEnvelope.Write(c.Key)
	hEnvelope.Write(c.REnc)
	hEnvelope.Write(c.Context)
	api.AssertIsEqual(hEnvelope.Sum(), c.KEnc)

	hBinding, err := stdmimc.NewMiMC(api)
	if err != nil {
		return err
	}
	hBinding.Write(c.CK)
	hBinding.Write(c.BuyerKey)
	hBinding.Write(c.KEnc)
	hBinding.Write(c.Context)
	hBinding.Write(KeyPurpose)
	api.AssertIsEqual(hBinding.Sum(), c.Binding)
	return nil
}

type DeliveryCircuit struct {
	Blocks  [BlockCount]frontend.Variable `gnark:",secret"`
	EncRand [BlockCount]frontend.Variable `gnark:",secret"`
	Key     frontend.Variable             `gnark:",secret"`
	RD      frontend.Variable             `gnark:",secret"`
	RK      frontend.Variable             `gnark:",secret"`

	CD      frontend.Variable `gnark:",public"`
	CK      frontend.Variable `gnark:",public"`
	Root    frontend.Variable `gnark:",public"`
	Context frontend.Variable `gnark:",public"`
	Binding frontend.Variable `gnark:",public"`
}

func (c *DeliveryCircuit) Define(api frontend.API) error {
	hD, err := stdmimc.NewMiMC(api)
	if err != nil {
		return err
	}
	for i := range c.Blocks {
		hD.Write(c.Blocks[i])
	}
	hD.Write(c.RD)
	api.AssertIsEqual(hD.Sum(), c.CD)

	hK, err := stdmimc.NewMiMC(api)
	if err != nil {
		return err
	}
	hK.Write(c.Key)
	hK.Write(c.RK)
	api.AssertIsEqual(hK.Sum(), c.CK)

	var leaves [BlockCount]frontend.Variable
	for i := 0; i < BlockCount; i++ {
		h, hashErr := stdmimc.NewMiMC(api)
		if hashErr != nil {
			return hashErr
		}
		h.Write(c.Key)
		h.Write(c.Blocks[i])
		h.Write(c.EncRand[i])
		leaves[i] = h.Sum()
	}

	level8 := hashPairs(api, leaves[:])
	level4 := hashPairs(api, level8)
	level2 := hashPairs(api, level4)
	level1 := hashPairs(api, level2)
	api.AssertIsEqual(level1[0], c.Root)

	hBinding, err := stdmimc.NewMiMC(api)
	if err != nil {
		return err
	}
	hBinding.Write(c.CD)
	hBinding.Write(c.CK)
	hBinding.Write(c.Root)
	hBinding.Write(c.Context)
	hBinding.Write(DeliveryPurpose)
	api.AssertIsEqual(hBinding.Sum(), c.Binding)
	return nil
}

func hashPairs(api frontend.API, values []frontend.Variable) []frontend.Variable {
	out := make([]frontend.Variable, len(values)/2)
	for i := 0; i < len(values); i += 2 {
		h, err := stdmimc.NewMiMC(api)
		if err != nil {
			panic(err)
		}
		h.Write(values[i])
		h.Write(values[i+1])
		out[i/2] = h.Sum()
	}
	return out
}

func Hash(values ...*big.Int) *big.Int {
	h := mimccrypto.NewMiMC()
	for _, value := range values {
		var element fr.Element
		element.SetBigInt(value)
		encoded := element.Bytes()
		_, _ = h.Write(encoded[:])
	}
	var result fr.Element
	result.SetBytes(h.Sum(nil))
	return result.BigInt(new(big.Int))
}

func RandomScalar() (*big.Int, error) {
	value, err := rand.Int(rand.Reader, ecc.BN254.ScalarField())
	if err != nil {
		return nil, fmt.Errorf("generate scalar: %w", err)
	}
	return value, nil
}

func DataCommitment(blocks [BlockCount]*big.Int, rD *big.Int) *big.Int {
	values := make([]*big.Int, 0, BlockCount+1)
	values = append(values, blocks[:]...)
	values = append(values, rD)
	return Hash(values...)
}

func QualityCommitment(blocks [BlockCount]*big.Int, rQ *big.Int) *big.Int {
	valid := big.NewInt(0)
	for i := 0; i < RecordCount; i++ {
		valid.Add(valid, blocks[i*4+2])
	}
	return Hash(valid, rQ)
}

func KeyCommitment(key, rK *big.Int) *big.Int {
	return Hash(key, rK)
}

func DeliveryRoot(blocks, encRand [BlockCount]*big.Int, key *big.Int) *big.Int {
	level := make([]*big.Int, BlockCount)
	for i := 0; i < BlockCount; i++ {
		level[i] = Hash(key, blocks[i], encRand[i])
	}
	for len(level) > 1 {
		next := make([]*big.Int, len(level)/2)
		for i := 0; i < len(level); i += 2 {
			next[i/2] = Hash(level[i], level[i+1])
		}
		level = next
	}
	return level[0]
}

func QualityBinding(cD, cQ, context *big.Int) *big.Int {
	return Hash(cD, cQ, context, big.NewInt(QualityPurpose))
}

func KeyEnvelope(buyerKey, key, rEnc, context *big.Int) *big.Int {
	return Hash(buyerKey, key, rEnc, context)
}

func KeyBinding(cK, buyerKey, kEnc, context *big.Int) *big.Int {
	return Hash(cK, buyerKey, kEnc, context, big.NewInt(KeyPurpose))
}

func DeliveryBinding(cD, cK, root, context *big.Int) *big.Int {
	return Hash(cD, cK, root, context, big.NewInt(DeliveryPurpose))
}
