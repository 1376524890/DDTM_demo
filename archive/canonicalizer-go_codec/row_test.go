package codec

import (
	"math"
	"testing"
)

func TestQuantizeDeterministic(t *testing.T) {
	q := Quantizer{Lower: -4, Upper: 4, Offset: 0, Scale: 1}
	v1, _ := Quantize(1.5, q)
	v2, _ := Quantize(1.5, q)
	if v1 != v2 {
		t.Fatalf("quantize not deterministic: %d != %d", v1, v2)
	}
}

func TestQuantizeClip(t *testing.T) {
	q := Quantizer{Lower: -2, Upper: 2, Offset: 0, Scale: 1}
	v, err := Quantize(5.0, q)
	if err != nil {
		t.Fatal(err)
	}
	v2, _ := Quantize(2.0, q)
	if v != v2 {
		t.Fatalf("clip failed: %d != %d", v, v2)
	}
}

func TestQuantizeNaN(t *testing.T) {
	q := Quantizer{Lower: -4, Upper: 4, Offset: 0, Scale: 1}
	_, err := Quantize(math.NaN(), q)
	if err == nil {
		t.Fatal("expected NaN error")
	}
}

func TestRowMarshalRoundTrip(t *testing.T) {
	row := Row{
		Version:   RowVersion,
		RowID:     42,
		Valid:     1,
		Label:     1,
		Timestamp: 1700000000,
	}
	row.Features[0] = 65536  // 1.0 in Q16.16
	row.Features[1] = 131072 // 2.0 in Q16.16
	row.MissingMask[0] = 0x01

	raw, err := row.MarshalBinary()
	if err != nil {
		t.Fatal(err)
	}
	if len(raw) != 548 {
		t.Fatalf("expected 548 bytes, got %d", len(raw))
	}

	// Second marshalling must be identical.
	raw2, err := row.MarshalBinary()
	if err != nil {
		t.Fatal(err)
	}
	for i := range raw {
		if raw[i] != raw2[i] {
			t.Fatalf("marshal not deterministic at byte %d", i)
		}
	}
}

func TestRowValidate(t *testing.T) {
	valid := Row{Version: RowVersion, Valid: 1, Label: 1}
	if err := valid.Validate(); err != nil {
		t.Fatal(err)
	}
	badLabel := Row{Version: RowVersion, Valid: 1, Label: 0}
	if err := badLabel.Validate(); err == nil {
		t.Fatal("expected error for label=0")
	}
	padding := Row{Version: RowVersion, Valid: 0, Label: 0}
	if err := padding.Validate(); err != nil {
		t.Fatal(err)
	}
	paddingBad := Row{Version: RowVersion, Valid: 0, Label: 1}
	if err := paddingBad.Validate(); err == nil {
		t.Fatal("expected error for padding with label")
	}
}

func TestPackFeaturesDeterministic(t *testing.T) {
	var features [FeatureCount]int32
	features[0] = 65536
	features[1] = -65536
	p1 := PackFeatures(features)
	p2 := PackFeatures(features)
	if len(p1) != 19 {
		t.Fatalf("expected 19 packed elements, got %d", len(p1))
	}
	for i := range p1 {
		if p1[i].Cmp(p2[i]) != 0 {
			t.Fatalf("packing not deterministic at %d", i)
		}
	}
}

func TestEncodeLabel(t *testing.T) {
	if EncodeLabel(-1) != 1 {
		t.Fatal("expected -1 -> 1")
	}
	if EncodeLabel(1) != 2 {
		t.Fatal("expected 1 -> 2")
	}
	if EncodeLabel(0) != 0 {
		t.Fatal("expected 0 -> 0")
	}
}

func TestMaskLimbs(t *testing.T) {
	var mask [16]byte
	mask[0] = 0xFF
	mask[15] = 0x80
	lo, hi := MaskLimbs(mask)
	if lo != 0xFF {
		t.Fatalf("expected lo=0xFF, got %d", lo)
	}
	if hi>>56 != 0x80 {
		t.Fatalf("expected hi high bit set")
	}
}

func TestRowMarshalBitFlip(t *testing.T) {
	row := Row{Version: RowVersion, RowID: 0, Valid: 1, Label: 1, Timestamp: 1700000000}
	b1, _ := row.MarshalBinary()
	row.Label = -1
	b2, _ := row.MarshalBinary()
	same := true
	for i := range b1 {
		if b1[i] != b2[i] {
			same = false
			break
		}
	}
	if same {
		t.Fatal("label change should change marshalled bytes")
	}
}
