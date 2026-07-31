"""IEEE-754 float32 → Q16.16 定点数的精确量化。

转换基于 float32 的*位模式*，而非浮点乘法，因此舍入可证明为 ties-to-even，
且跨语言完全一致。NaN、+Inf、-Inf 一律拒绝（``NON_FINITE_FEATURE``）：只有普通
有限数才会被裁剪到 schema 的上下界。
"""
from __future__ import annotations

import struct

# Schema 边界（Q16.16 以有符号 int32 存储）。能装入 int32 的自然 Q16.16 范围
# 恰好是 [-2^31, 2^31-1]，即实数 [-32768.0, 32767.99998…]。
LOWER_Q16 = -(1 << 31)
UPPER_Q16 = (1 << 31) - 1

# 错误码，与 specs/error-codes-v1.json 一致。
NON_FINITE_FEATURE = "NON_FINITE_FEATURE"


class NonFiniteFeature(ValueError):
    """输入为 NaN 或 ±Inf 时抛出。映射为 NON_FINITE_FEATURE。"""


def float32_bits(value: float) -> int:
    """返回 ``value`` 收窄为 float32 后的原始 32 位 IEEE-754 位模式。"""
    raw = struct.pack("<f", value)
    return struct.unpack("<I", raw)[0]


def round_div_power_of_two_even(numerator: int, shift: int) -> int:
    """用 ties-to-even 舍入将 ``numerator`` 除以 ``2**shift``。

    在幅值上运算后再重新套用符号，使负分子的行为与硬件 ties-to-even 完全一致。
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
        # 恰好为一半：舍入到最近的偶数商。
        quotient += 1

    return -quotient if negative else quotient


def f32_bits_to_q16(bits: int, lower_q16: int, upper_q16: int) -> int:
    """把 float32 位模式转换为裁剪后的 Q16.16 整数。

    若位模式编码的是 NaN 或 ±Inf，抛出 :class:`NonFiniteFeature`。
    """
    sign = (bits >> 31) & 1
    exponent = (bits >> 23) & 0xFF
    fraction = bits & 0x7FFFFF

    # 指数全 1 ⇒ NaN 或 Infinity。永不规范、永不裁剪。
    if exponent == 0xFF:
        raise NonFiniteFeature(
            "NaN and Infinity are not canonical inputs"
        )

    if exponent == 0:
        # 非正规数：value = fraction * 2^-149。
        mantissa = fraction
        binary_shift_after_q16 = -149 + 16
    else:
        # 正规数：value = (1.fraction) * 2^(exponent-127) = mantissa * 2^-150，
        # 其中 mantissa = 1.fraction（带隐式前导 1）。
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
    """把一个有限浮点数量化为裁剪后的 Q16.16 int32。"""
    return f32_bits_to_q16(float32_bits(value), LOWER_Q16, UPPER_Q16)
