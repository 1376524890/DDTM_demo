"""Poseidon2 BN254（width 4）置换与域标签 sponge ``H_P``。

常量是 gnark-crypto v0.20.1 BN254 width-4 的*经审计、硬编码*常量，已导出到
``specs/poseidon2-bn254-v1.json``。这里的置换用纯整数算术重新实现，使 Python 产生
与 gnark-crypto（进而 gnark）完全相同的域元素。导入时会重新推导打包的 KAT 向量，
任一不匹配即中止——这就是跨语言正确性契约。

``H_P(tag, elements)`` 通过 width-4 置换之上的 rate-3 sponge 吸收
``[tag, arity, *elements]``（初始状态全零，最后一块以零填充）并挤压出第 0 个元素。
显式的 ``arity`` 字段可防止不同长度输入之间的长度扩展歧义。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

try:
    import gmpy2  # type: ignore

    _HAS_GMPY2 = True
except ImportError:  # pragma: no cover - gmpy2 是推荐的运行时硬依赖
    _HAS_GMPY2 = False

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMS_PATH = REPO_ROOT / "specs" / "poseidon2-bn254-v1.json"

_raw = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
MODULUS = int(_raw["modulus"], 16)
WIDTH = _raw["width"]
FULL_ROUNDS = _raw["full_rounds"]
PARTIAL_ROUNDS = _raw["partial_rounds"]
_HALF_FULL = FULL_ROUNDS // 2
# 内部矩阵的对角线（mu_i - 1）。
_DIAG = tuple(int(x, 16) for x in _raw["diag_m1"])
# 轮密钥；对于硬编码的 width-4 集合，轮 i 的 len(RK[i]) == WIDTH（partial 轮存
# [key, 0, 0, 0]，因此加全部四个对尾部零是 no-op——与 gnark-crypto 的
# addRoundKeyInPlace 完全一致）。
_RK = tuple(tuple(int(x, 16) for x in rnd) for rnd in _raw["round_keys"])


def _to_mpz(value: int):
    return gmpy2.mpz(value) if _HAS_GMPY2 else value


P = _to_mpz(MODULUS)
_DIAG_Z = tuple(_to_mpz(v) for v in _DIAG)
_RK_Z = tuple(tuple(_to_mpz(v) for v in rnd) for rnd in _RK)


def _sbox(x):
    """x^5 mod p（平方、平方、相乘）。"""
    return (x * x * x * x * x) % P  # 4 次乘法；与 pow(x,5,P) 等价。


def _mat_external(s):
    """width 4 的外部矩阵：M4 循环矩阵（无跨块求和）。"""
    t0 = (s[0] + s[1]) % P
    t1 = (s[2] + s[3]) % P
    t2 = (2 * s[1] + t1) % P
    t3 = (2 * s[3] + t0) % P
    t4 = (4 * t1 + t3) % P
    t5 = (4 * t0 + t2) % P
    return [(t3 + t5) % P, t5, (t2 + t4) % P, t4]


def _mat_internal(s):
    """内部矩阵：input[i] * DiagM1[i] + sum(input)。"""
    tot = (s[0] + s[1] + s[2] + s[3]) % P
    return [(s[i] * _DIAG_Z[i] + tot) % P for i in range(WIDTH)]


def _add_round_key(round_index, s):
    rk = _RK_Z[round_index]
    return [(s[i] + rk[i]) % P for i in range(len(rk))]


def permute(state: Sequence[int]) -> list[int]:
    """对 4 元素状态施加 width-4 Poseidon2 置换。

    这是热点路径，故轮结构被内联：矩阵运算手写展开，能增长时才取模，模数与轮密钥
    重绑定为局部变量。算术与 gnark-crypto 的置换完全一致（由 KAT 自检验证）。
    """
    p = P
    s0 = _to_mpz(state[0]) % p
    s1 = _to_mpz(state[1]) % p
    s2 = _to_mpz(state[2]) % p
    s3 = _to_mpz(state[3]) % p

    def external(s0, s1, s2, s3):
        t0 = s0 + s1
        t1 = s2 + s3
        t2 = t1 + (s1 << 1)
        t3 = t0 + (s3 << 1)
        t4 = (t1 << 2) + t3
        t5 = (t0 << 2) + t2
        return (t3 + t5) % p, t5 % p, (t2 + t4) % p, t4 % p

    # 初始外部矩阵（M4）。
    s0, s1, s2, s3 = external(s0, s1, s2, s3)

    rk = _RK_Z
    diag = _DIAG_Z
    hf = _HALF_FULL
    end_partial = hf + PARTIAL_ROUNDS
    total = FULL_ROUNDS + PARTIAL_ROUNDS

    # 前半 full 轮：addRoundKey + sBox(all) + external。
    for i in range(hf):
        r = rk[i]
        s0 = (s0 + r[0]) % p
        s1 = (s1 + r[1]) % p
        s2 = (s2 + r[2]) % p
        s3 = (s3 + r[3]) % p
        a = s0 * s0 % p
        s0 = a * a % p * s0 % p  # x^5
        a = s1 * s1 % p
        s1 = a * a % p * s1 % p
        a = s2 * s2 % p
        s2 = a * a % p * s2 % p
        a = s3 * s3 % p
        s3 = a * a % p * s3 % p
        s0, s1, s2, s3 = external(s0, s1, s2, s3)

    # partial 轮：addRoundKey(0) + sBox(0) + internal。
    for i in range(hf, end_partial):
        s0 = (s0 + rk[i][0]) % p
        a = s0 * s0 % p
        s0 = a * a % p * s0 % p
        tot = (s0 + s1 + s2 + s3) % p
        s0 = (s0 * diag[0] + tot) % p
        s1 = (s1 * diag[1] + tot) % p
        s2 = (s2 * diag[2] + tot) % p
        s3 = (s3 * diag[3] + tot) % p

    # 后半 full 轮。
    for i in range(end_partial, total):
        r = rk[i]
        s0 = (s0 + r[0]) % p
        s1 = (s1 + r[1]) % p
        s2 = (s2 + r[2]) % p
        s3 = (s3 + r[3]) % p
        a = s0 * s0 % p
        s0 = a * a % p * s0 % p
        a = s1 * s1 % p
        s1 = a * a % p * s1 % p
        a = s2 * s2 % p
        s2 = a * a % p * s2 % p
        a = s3 * s3 % p
        s3 = a * a % p * s3 % p
        s0, s1, s2, s3 = external(s0, s1, s2, s3)

    return [int(s0), int(s1), int(s2), int(s3)]


def hash_poseidon(tag: int, elements: Sequence[int]) -> int:
    """``H_P(tag, elements)``——域标签、带 arity 的 sponge。"""
    # message = [tag, arity, *elements]；arity 字段记录 len(elements)。
    msg = [tag % P, _to_mpz(len(elements))]
    msg.extend(_to_mpz(e) % P for e in elements)

    state = [_to_mpz(0)] * WIDTH
    idx = 0
    n = len(msg)
    while idx < n:
        block = msg[idx : idx + 3]
        for j, value in enumerate(block):
            state[j] = (state[j] + value) % P
        state = permute(state)
        state = [_to_mpz(v) for v in state]
        idx += 3
    return int(state[0])


def _self_check() -> None:
    """重新推导每一个打包的 KAT 向量；任一不匹配即中止。"""
    for kat in _raw["kat"]:
        got = permute([int(x, 16) for x in kat["input"]])
        expected = [int(x, 16) for x in kat["output"]]
        if got != expected:
            raise RuntimeError(
                f"Poseidon2 KAT mismatch:\n  input={kat['input']}\n  "
                f"got={got}\n  expected={expected}"
            )


# 若我们的置换与 gnark-crypto 不一致，在导入时立即失败。
_self_check()
