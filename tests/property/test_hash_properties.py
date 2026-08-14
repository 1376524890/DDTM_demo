"""哈希属性测试（检查单 R/D）。

性质：H(x)=H(x)；H(x)=H(Deserialize(Serialize(x)))；逐字段修改 committed
输入 → H 变化（mutation testing）。
"""

from __future__ import annotations

import random

from valor.core.enums import DeliveryMode, ParamSource
from valor.core.hashing import content_hash
from valor.rights import RightsBundle

H64 = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3"


def _bundle(**over):
    base = dict(
        r_class="lic", access_mode=DeliveryMode.API_GATEWAY,
        t0="2025-01-01", t1="2025-12-31", q=10,
        purposes=frozenset({"ml"}), scope="CN",
        exclusivity=False, redistribution=False, derivative=False,
    )
    base.update(over)
    return RightsBundle(**base)


def test_hash_repeatable():
    x = {"a": [1, 2, 3], "b": "data"}
    assert content_hash(x) == content_hash(x)


def test_hash_roundtrip_preserved():
    rb = _bundle()
    restored = RightsBundle.from_plain(rb.to_plain())
    assert content_hash(rb) == content_hash(restored)


def test_mutation_changes_hash():
    """逐字段修改 committed 字段 → hash 必须变化（检查单 D tamper）。"""
    base = _bundle()
    base_hash = content_hash(base)
    mutations = [
        dict(q=99),
        dict(t0="2025-02-01"),
        dict(purposes=frozenset({"other"})),
        dict(scope="EU"),
        dict(exclusivity=True),
        dict(redistribution=True),
        dict(derivative=True),
        dict(r_class="other"),
        dict(t1="2026-01-01"),
    ]
    for over in mutations:
        mutated = _bundle(**over)
        assert content_hash(mutated) != base_hash, f"字段变化 hash 未变: {over}"


def test_random_objects_hash_distinct():
    """随机不同对象 → 哈希不同（工程级，非密码学证明）。"""
    rng = random.Random(42)
    hashes = set()
    for i in range(200):
        obj = {
            "id": i,
            "v": rng.random(),
            "s": rng.choice(["a", "b", "c"]),
        }
        hashes.add(content_hash(obj))
    assert len(hashes) == 200
