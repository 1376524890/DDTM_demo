package codec

import (
	"encoding/binary"
	"errors"
	"fmt"
	"math"
	"math/big"
)

const (
	FeatureCount            = 128
	MissingMaskBytes        = 16
	RowVersion       uint16 = 1
)

type Row struct {
	Version     uint16
	RowID       uint64
	Valid       uint8
	Label       int8
	Timestamp   uint64
	MissingMask [MissingMaskBytes]byte
	Features    [FeatureCount]int32
}

type Quantizer struct {
	Lower  float64 `json:"lower"`
	Upper  float64 `json:"upper"`
	Offset float64 `json:"offset"`
	Scale  float64 `json:"scale"`
}

func RoundHalfToEven(x float64) int64 {
	// math.RoundToEven is deterministic for finite IEEE-754 inputs.
	return int64(math.RoundToEven(x))
}

func Quantize(x float64, q Quantizer) (int32, error) {
	if math.IsNaN(x) || math.IsInf(x, 0) {
		return 0, errors.New("non-finite feature")
	}
	if q.Scale <= 0 {
		return 0, errors.New("scale must be positive")
	}
	if x < q.Lower {
		x = q.Lower
	}
	if x > q.Upper {
		x = q.Upper
	}
	z := ((x - q.Offset) / q.Scale) * 65536.0
	rounded := RoundHalfToEven(z)
	if rounded < math.MinInt32 || rounded > math.MaxInt32 {
		return 0, fmt.Errorf("quantized value out of int32: %d", rounded)
	}
	return int32(rounded), nil
}

func (r *Row) Validate() error {
	if r.Version != RowVersion {
		return fmt.Errorf("unsupported row version %d", r.Version)
	}
	if r.Valid > 1 {
		return errors.New("valid must be 0 or 1")
	}
	if r.Valid == 0 {
		if r.Label != 0 {
			return errors.New("padding row label must be 0")
		}
	} else if r.Label != -1 && r.Label != 1 {
		return errors.New("valid row label must be -1 or +1")
	}
	return nil
}

func (r *Row) MarshalBinary() ([]byte, error) {
	if err := r.Validate(); err != nil {
		return nil, err
	}
	// 2 + 8 + 1 + 1 + 8 + 16 + 128*4 = 548 bytes.
	out := make([]byte, 548)
	off := 0
	binary.LittleEndian.PutUint16(out[off:], r.Version)
	off += 2
	binary.LittleEndian.PutUint64(out[off:], r.RowID)
	off += 8
	out[off] = r.Valid
	off++
	out[off] = byte(r.Label)
	off++
	binary.LittleEndian.PutUint64(out[off:], r.Timestamp)
	off += 8
	copy(out[off:], r.MissingMask[:])
	off += MissingMaskBytes
	for _, v := range r.Features {
		binary.LittleEndian.PutUint32(out[off:], uint32(v))
		off += 4
	}
	return out, nil
}

func PackFeatures(features [FeatureCount]int32) []*big.Int {
	const perField = 7
	packed := make([]*big.Int, 0, 19)
	for base := 0; base < FeatureCount; base += perField {
		acc := new(big.Int)
		for j := 0; j < perField && base+j < FeatureCount; j++ {
			// Offset encoding maps signed int32 to [0, 2^32-1].
			u := uint64(int64(features[base+j]) + (1 << 31))
			term := new(big.Int).SetUint64(u)
			term.Lsh(term, uint(32*j))
			acc.Or(acc, term)
		}
		packed = append(packed, acc)
	}
	return packed
}

func MaskLimbs(mask [MissingMaskBytes]byte) (uint64, uint64) {
	return binary.LittleEndian.Uint64(mask[:8]), binary.LittleEndian.Uint64(mask[8:])
}

func EncodeLabel(label int8) uint64 {
	switch label {
	case -1:
		return 1
	case 1:
		return 2
	default:
		return 0
	}
}
