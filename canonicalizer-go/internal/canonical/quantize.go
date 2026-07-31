package canonical

import (
	"errors"
	"math"
)

// Q16.16 存储边界（有符号 int32 范围）。
const (
	LowerQ16 = -2147483648
	UpperQ16 = 2147483647
)

// ErrNonFinite 在遇到 NaN / ±Inf 时返回。映射为 NON_FINITE_FEATURE。
var ErrNonFinite = errors.New("NON_FINITE_FEATURE")

// roundDivPow2Even 用 ties-to-even 舍入把 numerator 除以 2^shift，在幅值上运算后
// 再重新套用符号。
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

// F32BitsToQ16 把一个 IEEE-754 float32 位模式转换为裁剪后的 Q16.16 int32。
// NaN/±Inf（exp == 0xFF）被拒绝。
func F32BitsToQ16(bits uint32) (int32, error) {
	sign := (bits >> 31) & 1
	exponent := (bits >> 23) & 0xFF
	fraction := bits & 0x7FFFFF

	if exponent == 0xFF {
		return 0, ErrNonFinite
	}

	var mantissa int64
	var shift int // Q16 缩放后施加的移位
	if exponent == 0 {
		// 非正规数：value = fraction * 2^-149
		mantissa = int64(fraction)
		shift = -149 + 16
	} else {
		// 正规数：带隐式 1 的 mantissa，value = mantissa * 2^(exp-150)
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

// Quantize 把一个浮点数收窄为 float32，再转换为裁剪后的 Q16.16 int32。
func Quantize(value float32) (int32, error) {
	return F32BitsToQ16(math.Float32bits(value))
}
