"""检测能力认证测试（规范 §22/§67）。"""

from __future__ import annotations

import pytest

from valor.core.errors import ProfileOutOfCertifiedRangeError
from valor.security.certification import (
    CertifiedCell,
    CertificationCatalog,
    certification_sample_size,
)


def _catalog():
    cat = CertificationCatalog()
    cat.register(CertifiedCell(
        cell_id="c1", a_D=1.0, b_D=1.0, alpha_D=0.05,
        families={"structural_breach": (10, 2), "label_breach": (8, 4)},
    ))
    return cat


def test_p_breach_lower():
    cat = _catalog()
    lo = cat.p_breach_lower("c1", "structural_breach")
    assert 0.0 < lo < 1.0
    # 保守下界应随样本增加而升高（更多 TP → 更接近真实检出率）
    cat2 = CertificationCatalog()
    cat2.register(CertifiedCell(
        "c1", 1.0, 1.0, 0.05, {"s": (100, 2)}
    ))
    assert cat2.p_breach_lower("c1", "s") > lo


def test_certified_pB_sys_min_over_families():
    cat = _catalog()
    p = cat.certified_pB_sys("c1", ["structural_breach", "label_breach"])
    lo_s = cat.p_breach_lower("c1", "structural_breach")
    lo_l = cat.p_breach_lower("c1", "label_breach")
    assert p == pytest.approx(min(lo_s, lo_l))


def test_out_of_certified_range():
    cat = _catalog()
    with pytest.raises(ProfileOutOfCertifiedRangeError):
        cat.get("nope")


def test_sample_size_search():
    n = certification_sample_size(
        a_D=1.0, b_D=1.0, alpha_D=0.05, p_target=0.9, fn_allow=2
    )
    assert n >= 1
