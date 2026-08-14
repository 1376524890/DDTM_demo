"""valor/core 单元测试：canonical JSON / hashing / money / errors / ids。

对齐规范 §5.3、§12、§4、§33。
"""

from __future__ import annotations

import pytest

from valor.core.canonical_json import canonical_dumps, canonicalize
from valor.core.errors import UnitMismatchError
from valor.core.hashing import content_hash, stable_hash
from valor.core.ids import InvalidIDError, new_id, validate_id
from valor.core.money import CURRENCY_UNIT, Money, to_cu


def test_canonical_dumps_deterministic():
    a = {"b": 1, "a": [3, 2, 1], "c": None}
    b = {"a": [3, 2, 1], "c": None, "b": 1}
    assert canonical_dumps(a) == canonical_dumps(b)
    assert canonical_dumps(a) == '{"a":[3,2,1],"b":1,"c":null}'


def test_canonicalize_enum_and_dataclass():
    from valor.core.enums import TradeState

    assert canonicalize(TradeState.GOOD) == "G"


def test_content_hash_stable():
    assert content_hash({"k": [1, 2]}) == content_hash({"k": [1, 2]})
    assert len(content_hash({"x": 1})) == 64


def test_stable_hash_chain():
    """哈希链 h_t = H(h_{t-1} ∥ canonical(e_t)) 可验证（§33）。"""
    e1 = {"action": "READ", "actor": "b1"}
    e2 = {"action": "WRITE", "actor": "b1"}
    h0 = stable_hash("genesis")
    h1 = stable_hash(h0, e1)
    h2 = stable_hash(h1, e2)
    # 重放同样事件序列得到一致链
    h1b = stable_hash(stable_hash("genesis"), e1)
    h2b = stable_hash(h1b, e2)
    assert h1 == h1b and h2 == h2b


def test_money_unit_enforced():
    a = to_cu(100)
    b = to_cu(25)
    assert (a + b).amount == 125
    assert a >= b
    # Money 只接受 [CU]；非 CU 单位在构造时即抛 UNIT_MISMATCH（§12）
    from valor.core.money import Money as M

    with pytest.raises(UnitMismatchError):
        M(10, "unitless")


def test_ids():
    tid = new_id("tx")
    assert tid.startswith("tx-")
    validate_id(tid)
    with pytest.raises(InvalidIDError):
        validate_id("BAD ID!")
