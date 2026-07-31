"""Exact IEEE-754 float32 → Q16.16 fixed-point quantization.

The conversion works on the float32 *bit pattern*, not on a float multiply, so
the rounding is provably ties-to-even and identical across languages. NaN,
+Inf and -Inf are rejected outright (``NON_FINITE_FEATURE``): only ordinary
finite numbers are clamped to the schema bounds.
"""
from __future__ import annotations

import struct

# Schema bounds (Q16.16 stored as signed int32). The natural Q16.16 range that
# fits in int32 is exactly [-2^31, 2^31-1] == real [-32768.0, 32767.99998…].
LOWER_Q16 = -(1 << 31)
UPPER_Q16 = (1 << 31) - 1

# Error code matching specs/error-codes-v1.json.
NON_FINITE_FEATURE = "NON_FINITE_FEATURE"


class NonFiniteFeature(ValueError):
    """Raised when an input is NaN or ±Inf. Maps to NON_FINITE_FEATURE."""


def float32_bits(value: float) -> int:
    """Return the raw 32-bit IEEE-754 pattern of ``value`` narrowed to float32."""
    raw = struct.pack("<f", value)
    return struct.unpack("<I", raw)[0]


def round_div_power_of_two_even(numerator: int, shift: int) -> int:
    """Divide ``numerator`` by ``2**shift`` with ties-to-even rounding.

    Operates on the magnitude and re-applies the sign so the behaviour is
    identical to hardware ties-to-even for negative numerators.
    """
    if shift <= 0:
        return numerator << (-shift)

    negative = numerator < 0
    magnitude = abs(numerator)

    denominator = 1 << shift
    quotient, remainder = divmod(magnitude, denominator)
    half = denominator >> 1

    if remainder > half:
        quotient += 1
    elif remainder == half and quotient % 2 == 1:
        # Exact half: round to the nearest even quotient.
        quotient += 1

    return -quotient if negative else quotient


def f32_bits_to_q16(bits: int, lower_q16: int, upper_q16: int) -> int:
    """Convert a float32 bit pattern to a clamped Q16.16 integer.

    Raises :class:`NonFiniteFeature` if the pattern encodes NaN or ±Inf.
    """
    sign = (bits >> 31) & 1
    exponent = (bits >> 23) & 0xFF
    fraction = bits & 0x7FFFFF

    # Exponent all-ones ⇒ NaN or Infinity. Never canonical, never clamped.
    if exponent == 0xFF:
        raise NonFiniteFeature(
            "NaN and Infinity are not canonical inputs"
        )

    if exponent == 0:
        # Subnormal: value = fraction * 2^-149.
        mantissa = fraction
        binary_shift_after_q16 = -149 + 16
    else:
        # Normal: value = (1.fraction) * 2^(exponent-127) = mantissa * 2^-150
        # where mantissa = 1.fraction with the implicit leading 1.
        mantissa = (1 << 23) | fraction
        binary_shift_after_q16 = exponent - 150 + 16

    signed_mantissa = -mantissa if sign else mantissa

    if binary_shift_after_q16 >= 0:
        quantized = signed_mantissa << binary_shift_after_q16
    else:
        quantized = round_div_power_of_two_even(
            signed_mantissa, -binary_shift_after_q16
        )

    return min(max(quantized, lower_q16), upper_q16)


def quantize(value: float) -> int:
    """Quantize a finite float to a clamped Q16.16 int32."""
    return f32_bits_to_q16(float32_bits(value), LOWER_Q16, UPPER_Q16)
