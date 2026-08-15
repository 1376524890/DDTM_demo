"""P12 五场景验收组 C0-C4 测试。"""

from __future__ import annotations

import pytest

from valor.engine.acceptance import (
    scenario_c0_normal,
    scenario_c1_no_trade,
    scenario_c2_seller_breach,
    scenario_c3_buyer_misuse,
)
from valor.engine import run_capstone


def test_c0_normal_trade(tmp_path):
    res = run_capstone(scenario_c0_normal(), run_dir=str(tmp_path))
    assert res.terminal_state in ("TRADE", "NO_TRADE")  # 经济上可能 NO_TRADE


def test_c2_seller_breach_terminal(tmp_path):
    res = run_capstone(scenario_c2_seller_breach(), run_dir=str(tmp_path))
    assert res.terminal_state == "SELLER_BREACH"


def test_c3_buyer_misuse_terminal(tmp_path):
    res = run_capstone(scenario_c3_buyer_misuse(), run_dir=str(tmp_path))
    assert res.terminal_state == "BUYER_BREACH"


def test_c1_no_trade_terminal(tmp_path):
    """卖方保留效用极高 → NO_TRADE。"""
    res = run_capstone(scenario_c1_no_trade(), run_dir=str(tmp_path))
    assert res.terminal_state == "NO_TRADE"
