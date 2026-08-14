"""canonicalization 属性测试（检查单 R）。

性质：Canonicalize(x)=Canonicalize(x)；key 顺序无关；set 顺序无关；
tuple/list 语义稳定；跨"进程"重复一致。
"""

from __future__ import annotations

import random

from valor.core.canonical_json import canonical_bytes, canonical_dumps, canonicalize
from valor.core.hashing import content_hash


def test_idempotent():
    x = {"a": [1, 2], "b": {"c": None, "d": "héllo"}}
    assert canonical_bytes(x) == canonical_bytes(x)


def test_key_order_invariant_random():
    rng = random.Random(0)
    keys = ["k%d" % i for i in range(50)]
    base = {k: i for i, k in enumerate(keys)}
    for _ in range(20):
        shuffled = list(keys)
        rng.shuffle(shuffled)
        d = {k: base[k] for k in shuffled}
        assert canonical_bytes(base) == canonical_bytes(d)


def test_set_order_invariant():
    a = canonical_bytes({"s": {1, 2, 3}})
    b = canonical_bytes({"s": {3, 1, 2}})  # 不同插入/迭代顺序
    assert a == b


def test_tuple_list_semantics():
    # 明确规则：tuple/list 都规范化为 list
    assert canonical_bytes((1, 2)) == canonical_bytes([1, 2])
    assert canonical_bytes({"t": (1, 2)}) == canonical_bytes({"t": [1, 2]})


def test_none_and_unicode():
    assert canonical_bytes(None) == b"null"
    assert canonical_bytes({"s": "héllo"}) == canonical_bytes({"s": "héllo"})
    # NFC 归一化：组合形式与预组合形式一致
    assert canonical_bytes({"s": "e\u0301"}) == canonical_bytes({"s": "é"})


def test_hash_stable_across_rebuild():
    """H(x)=H(x)；重复计算一致（检查单 R）。"""
    x = {"x": 1, "y": [2, 3], "z": {"n": None}}
    assert content_hash(x) == content_hash(x)
    assert content_hash(canonicalize(x)) == content_hash(x)
