package canonical

import (
	"encoding/binary"
	"fmt"
)

// Row layout constants (row-layout-v1), little-endian, 548 bytes total.
const (
	RowSize        = 548
	FeatureCount   = 128
	MaskSize       = 16
	ReservedOffset = 546
)

// Row is a decoded canonical row. Features are Q16.16 int32 values.
type Row struct {
	RowID       uint64
	Timestamp   uint64
	Features    [FeatureCount]int32
	MissingMask [MaskSize]byte
	Label       int8
	Valid       uint8
}

// Encode serializes a validated row to exactly 548 bytes.
func (r *Row) Encode() ([]byte, error) {
	if err := r.Validate(); err != nil {
		return nil, err
	}
	out := make([]byte, RowSize)
	binary.LittleEndian.PutUint64(out[0:8], r.RowID)
	binary.LittleEndian.PutUint64(out[8:16], r.Timestamp)
	for i, f := range r.Features {
		binary.LittleEndian.PutUint32(out[16+i*4:20+i*4], uint32(f))
	}
	copy(out[528:544], r.MissingMask[:])
	out[544] = byte(r.Label)
	out[545] = r.Valid
	// reserved stays zero.
	return out, nil
}

// Decode parses 548 bytes into a validated row.
func DecodeRow(blob []byte) (*Row, error) {
	if len(blob) != RowSize {
		return nil, fmt.Errorf("expected %d bytes, got %d", RowSize, len(blob))
	}
	if binary.LittleEndian.Uint16(blob[546:548]) != 0 {
		return nil, fmt.Errorf("RESERVED_NONZERO")
	}
	r := &Row{}
	r.RowID = binary.LittleEndian.Uint64(blob[0:8])
	r.Timestamp = binary.LittleEndian.Uint64(blob[8:16])
	for i := 0; i < FeatureCount; i++ {
		r.Features[i] = int32(binary.LittleEndian.Uint32(blob[16+i*4 : 20+i*4]))
	}
	copy(r.MissingMask[:], blob[528:544])
	r.Label = int8(blob[544])
	r.Valid = blob[545]
	if err := r.Validate(); err != nil {
		return nil, err
	}
	return r, nil
}

// Validate checks the field constraints.
func (r *Row) Validate() error {
	if r.Valid > 1 {
		return fmt.Errorf("INVALID_VALID_FLAG")
	}
	if r.Valid == 1 && r.Label != -1 && r.Label != 1 {
		return fmt.Errorf("INVALID_LABEL")
	}
	return nil
}

// PaddingRow builds the deterministic padding row placed at leafIndex.
func PaddingRow(leafIndex uint64) *Row {
	return &Row{
		RowID:       leafIndex,
		Timestamp:   0,
		MissingMask: [MaskSize]byte{0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
			0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		Label: -1,
		Valid: 0,
	}
}
