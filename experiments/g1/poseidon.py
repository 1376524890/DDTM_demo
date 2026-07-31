"""Poseidon2 BN254 (width 4) permutation and the ``H_P`` domain-tagged sponge.

The constants are the *audited, hardcoded* gnark-crypto v0.20.1 BN254 width-4
constants, exported to ``specs/poseidon2-bn254-v1.json``. The permutation is
reimplemented here in pure integer arithmetic so that Python produces the
exact same field elements as gnark-crypto (and thus gnark). On import the
implementation re-derives the bundled KAT vectors and aborts if any mismatch
is detected — that is the cross-language correctness contract.

``H_P(tag, elements)`` absorbs ``[tag, arity, *elements]`` through a rate-3
sponge over the width-4 permutation (zero initial state, final block
zero-padded) and squeezes element 0. The explicit ``arity`` field prevents
length-extension ambiguity between inputs of different lengths.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

try:
    import gmpy2  # type: ignore

    _HAS_GMPY2 = True
except ImportError:  # pragma: no cover - gmpy2 is a hard runtime recommendation
    _HAS_GMPY2 = False

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMS_PATH = REPO_ROOT / "specs" / "poseidon2-bn254-v1.json"

_raw = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
MODULUS = int(_raw["modulus"], 16)
WIDTH = _raw["width"]
FULL_ROUNDS = _raw["full_rounds"]
PARTIAL_ROUNDS = _raw["partial_rounds"]
_HALF_FULL = FULL_ROUNDS // 2
# Diagonal of the internal matrix (mu_i - 1).
_DIAG = tuple(int(x, 16) for x in _raw["diag_m1"])
# Round keys; round i has len(RK[i]) == WIDTH for the hardcoded width-4 set
# (partial rounds store [key, 0, 0, 0], so adding all four is a no-op on the
# trailing zeros — matching gnark-crypto's addRoundKeyInPlace exactly).
_RK = tuple(tuple(int(x, 16) for x in rnd) for rnd in _raw["round_keys"])


def _to_mpz(value: int):
    return gmpy2.mpz(value) if _HAS_GMPY2 else value


P = _to_mpz(MODULUS)
_DIAG_Z = tuple(_to_mpz(v) for v in _DIAG)
_RK_Z = tuple(tuple(_to_mpz(v) for v in rnd) for rnd in _RK)


def _sbox(x):
    """x^5 mod p (square, square, multiply)."""
    return (x * x * x * x * x) % P  # 4 muls; pow(x,5,P) is equivalent.


def _mat_external(s):
    """External matrix for width 4: the M4 circulant (no cross-block sum)."""
    t0 = (s[0] + s[1]) % P
    t1 = (s[2] + s[3]) % P
    t2 = (2 * s[1] + t1) % P
    t3 = (2 * s[3] + t0) % P
    t4 = (4 * t1 + t3) % P
    t5 = (4 * t0 + t2) % P
    return [(t3 + t5) % P, t5, (t2 + t4) % P, t4]


def _mat_internal(s):
    """Internal matrix: input[i] * DiagM1[i] + sum(input)."""
    tot = (s[0] + s[1] + s[2] + s[3]) % P
    return [(s[i] * _DIAG_Z[i] + tot) % P for i in range(WIDTH)]


def _add_round_key(round_index, s):
    rk = _RK_Z[round_index]
    return [(s[i] + rk[i]) % P for i in range(len(rk))]


def permute(state: Sequence[int]) -> list[int]:
    """Apply the Poseidon2 width-4 permutation to a 4-element state.

    Hot path: the round structure is inlined, mat-ops are written out by hand,
    reductions are deferred where safe, and constants are rebound as locals.
    Arithmetic mirrors gnark-crypto exactly (KAT-verified at import).
    """
    p = P
    rk = _RK_Z
    diag = _DIAG_Z
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

    # Initial external matrix.
    s0, s1, s2, s3 = external(s0, s1, s2, s3)

    hf = _HALF_FULL
    end_partial = hf + PARTIAL_ROUNDS
    total = FULL_ROUNDS + PARTIAL_ROUNDS

    # First half of full rounds: addRoundKey + sBox(all) + external.
    for i in range(hf):
        r = rk[i]
        s0 = (s0 + r[0]) % p
        s1 = (s1 + r[1]) % p
        s2 = (s2 + r[2]) % p
        s3 = (s3 + r[3]) % p
        # x^5 = x2 * x4 ; three muls, reduced.
        a = s0 * s0 % p
        s0 = a * a % p * s0 % p
        a = s1 * s1 % p
        s1 = a * a % p * s1 % p
        a = s2 * s2 % p
        s2 = a * a % p * s2 % p
        a = s3 * s3 % p
        s3 = a * a % p * s3 % p
        s0, s1, s2, s3 = external(s0, s1, s2, s3)

    # Partial rounds: addRoundKey(0) + sBox(0) + internal.
    for i in range(hf, end_partial):
        s0 = (s0 + rk[i][0]) % p
        a = s0 * s0 % p
        s0 = a * a % p * s0 % p
        tot = (s0 + s1 + s2 + s3) % p
        s0 = (s0 * diag[0] + tot) % p
        s1 = (s1 * diag[1] + tot) % p
        s2 = (s2 * diag[2] + tot) % p
        s3 = (s3 * diag[3] + tot) % p

    # Second half of full rounds.
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
    """``H_P(tag, elements)`` — the domain-tagged, arity-separated sponge."""
    # Message = [tag, arity, *elements]; the arity field records len(elements).
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
    """Re-derive every bundled KAT vector; abort if any disagree."""
    for kat in _raw["kat"]:
        got = permute([int(x, 16) for x in kat["input"]])
        expected = [int(x, 16) for x in kat["output"]]
        if got != expected:
            raise RuntimeError(
                f"Poseidon2 KAT mismatch:\n  input={kat['input']}\n  "
                f"got={got}\n  expected={expected}"
            )


# Fail fast at import time if our permutation diverges from gnark-crypto.
_self_check()
