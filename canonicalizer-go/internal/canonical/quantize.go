package canonical

import (
	"errors"
	"math"
)

// Q16.16 storage bounds (signed int32 range).
const (
	LowerQ16 = -2147483648
	UpperQ16 = 2147483647
)

// ErrNonFinite is returned for NaN / ±Inf inputs. Maps to NON_FINITE_FEATURE.
var ErrNonFinite = errors.New("NON_FINITE_FEATURE")

// roundDivPow2Even divides numerator by 2^shift with ties-to-even rounding,
// operating on the magnitude and re-applying the sign.
func roundDivPow2Even(numerator, shift int) int {
	if shift <= 0 {
		return numerator << uint(-shift)
	}
	negative := numerator < 0
	magnitude := numerator
	if negative {
		magnitude = -numerator
	}
	denominator := 1 << uint(shift)
	quotient := magnitude / denominator
	remainder := magnitude % denominator
	half := denominator >> 1
	if remainder > half {
		quotient++
	} else if remainder == half && quotient%2 == 1 {
		quotient++
	}
	if negative {
		return -quotient
	}
	return quotient
}

// F32BitsToQ16 converts an IEEE-754 float32 bit pattern to a clamped Q16.16
// int32. NaN/±Inf (exp == 0xFF) are rejected.
func F32BitsToQ16(bits uint32) (int32, error) {
	sign := (bits >> 31) & 1
	exponent := (bits >> 23) & 0xFF
	fraction := bits & 0x7FFFFF

	if exponent == 0xFF {
		return 0, ErrNonFinite
	}

	var mantissa int64
	var shift int // shift to apply after the Q16 scaling
	if exponent == 0 {
		// subnormal: value = fraction * 2^-149
		mantissa = int64(fraction)
		shift = -149 + 16
	} else {
		// normal: mantissa with implicit 1, value = mantissa * 2^(exp-150)
		mantissa = int64(1<<23) | int64(fraction)
		shift = int(exponent) - 150 + 16
	}
	if sign == 1 {
		mantissa = -mantissa
	}

	var quantized int
	if shift >= 0 {
		quantized = int(mantissa) << uint(shift)
	} else {
		quantized = roundDivPow2Even(int(mantissa), -shift)
	}
	if quantized < LowerQ16 {
		quantized = LowerQ16
	}
	if quantized > UpperQ16 {
		quantized = UpperQ16
	}
	return int32(quantized), nil
}

// Quantize narrows a float to float32 and converts to clamped Q16.16 int32.
func Quantize(value float32) (int32, error) {
	return F32BitsToQ16(math.Float32bits(value))
}
