package circuits

import (
	"math/big"
	"testing"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/test"
)

func fixture() ([BlockCount]*big.Int, [BlockCount]*big.Int) {
	var blocks [BlockCount]*big.Int
	var randomness [BlockCount]*big.Int
	values := []int64{
		10, 1900, 1, 0,
		20, 1910, 1, 0,
		30, 1920, 1, 0,
		0, 1930, 0, 0,
	}
	for i := 0; i < BlockCount; i++ {
		blocks[i] = big.NewInt(values[i])
		randomness[i] = big.NewInt(int64(100 + i))
	}
	return blocks, randomness
}

func TestQualityCircuitDerivesMetricFromData(t *testing.T) {
	assert := test.NewAssert(t)
	blocks, _ := fixture()
	rD := big.NewInt(2001)
	rQ := big.NewInt(2002)
	context := big.NewInt(3001)
	cD := DataCommitment(blocks, rD)
	cQ := QualityCommitment(blocks, rQ)
	binding := QualityBinding(cD, cQ, context)

	valid := &QualityCircuit{
		RD: rD, RQ: rQ,
		CD: cD, CQ: cQ,
		MinPresent: 3, MaxValue: 100, MaxAge: 200, AsOfTime: 2000,
		Context: context, Binding: binding,
	}
	for i := range blocks {
		valid.Blocks[i] = blocks[i]
	}
	assert.SolvingSucceeded(&QualityCircuit{}, valid, test.WithCurves(ecc.BN254))

	invalid := *valid
	invalid.MinPresent = 4
	assert.SolvingFailed(&QualityCircuit{}, &invalid, test.WithCurves(ecc.BN254))
}

func TestKeyCircuitRejectsContextReplay(t *testing.T) {
	assert := test.NewAssert(t)
	key := big.NewInt(123)
	rK := big.NewInt(456)
	rEnc := big.NewInt(789)
	buyerKey := big.NewInt(321)
	context := big.NewInt(654)
	digestField := big.NewInt(987)
	cK := KeyCommitment(key, rK)
	envelope := KeyEnvelope(buyerKey, key, rEnc, context)
	binding := KeyBinding(cK, buyerKey, envelope, digestField, context)
	valid := &KeyCircuit{
		Key: key, RK: rK, REnc: rEnc,
		CK: cK, BuyerKey: buyerKey, KEnc: envelope,
		EnvelopeDigestField: digestField, Context: context, Binding: binding,
	}
	assert.SolvingSucceeded(&KeyCircuit{}, valid, test.WithCurves(ecc.BN254))

	invalid := *valid
	invalid.Context = big.NewInt(655)
	assert.SolvingFailed(&KeyCircuit{}, &invalid, test.WithCurves(ecc.BN254))
}

func TestDeliveryCircuitBindsRootAndObjectDigest(t *testing.T) {
	assert := test.NewAssert(t)
	blocks, encRand := fixture()
	key := big.NewInt(123)
	rD := big.NewInt(2001)
	rK := big.NewInt(2003)
	context := big.NewInt(3001)
	objectDigestField := big.NewInt(4001)
	cD := DataCommitment(blocks, rD)
	cK := KeyCommitment(key, rK)
	root := DeliveryRoot(blocks, encRand, key)
	binding := DeliveryBinding(cD, cK, root, objectDigestField, context)
	valid := &DeliveryCircuit{
		Key: key, RD: rD, RK: rK,
		CD: cD, CK: cK, Root: root,
		ObjectDigestField: objectDigestField, Context: context, Binding: binding,
	}
	for i := range blocks {
		valid.Blocks[i] = blocks[i]
		valid.EncRand[i] = encRand[i]
	}
	assert.SolvingSucceeded(&DeliveryCircuit{}, valid, test.WithCurves(ecc.BN254))

	invalid := *valid
	invalid.Root = big.NewInt(1)
	assert.SolvingFailed(&DeliveryCircuit{}, &invalid, test.WithCurves(ecc.BN254))
}
