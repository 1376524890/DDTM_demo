package circuits

import (
	"fmt"
	"github.com/consensys/gnark/frontend"
	poseidon "github.com/consensys/gnark/std/hash/poseidon2"
)

const (
	FeatureCount            = 128
	MerkleDepth             = 17
	AuditBatchSize          = 64
	SignedMetricBias uint64 = 1 << 62
	FeatureBias      uint64 = 1 << 31
	WeightBias       uint64 = 1 << 15
)

var (
	TagMetrics = frontend.Variable(0x444D5401)
	TagAudit   = frontend.Variable(0x44415501)
	TagRow     = frontend.Variable(0x44525401)
	TagNode    = frontend.Variable(0x444E4401)
	TagFeistel = frontend.Variable(0x44465001)
)

func Hash(api frontend.API, values ...frontend.Variable) (frontend.Variable, error) {
	h, err := poseidon.New(api)
	if err != nil {
		return nil, err
	}
	h.Write(values...)
	return h.Sum(), nil
}

func AssertBits(api frontend.API, value frontend.Variable, bits int) {
	api.ToBinary(value, bits)
}

func LessOrEqual(api frontend.API, left, right frontend.Variable, bits int) {
	AssertBits(api, left, bits)
	AssertBits(api, right, bits)
	api.AssertIsLessOrEqual(left, right)
}

func AssertBooleanArray(api frontend.API, values []frontend.Variable) {
	for _, v := range values {
		api.AssertIsBoolean(v)
	}
}

func SelectSignedLabel(api frontend.API, labelBit, value frontend.Variable) frontend.Variable {
	// labelBit=1 means +1; labelBit=0 means -1.
	api.AssertIsBoolean(labelBit)
	return api.Select(labelBit, value, api.Neg(value))
}

func requireOdd(value int, name string) error {
	if value%2 == 0 {
		return fmt.Errorf("%s must be odd", name)
	}
	return nil
}
