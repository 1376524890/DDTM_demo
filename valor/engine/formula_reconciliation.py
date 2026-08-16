"""FormulaReconciliationEngine —— 公式独立复算引擎（FullChainGate V2 核心）。

每个公式注册一个独立重算函数：输入是 stage 记录的 `recompute_inputs`（纯原始
输入，不含运行中间量），输出是独立复算值。Gate 用 engine 逐项对账，比较
「记录输出」与「独立重算」在容差内是否一致。

这使 Gate 从"字段存在/数值非负"升级为"真正独立复算"，论文意义上可证明。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np


@dataclass
class ReconciliationRule:
    """一条公式对账规则。"""

    formula_id: str
    output_key: str  # stage output 中要验证的键
    recompute_fn: Callable[[dict], float]  # 输入 recompute_inputs → 独立复算值
    tolerance: float = 1e-6
    description: str = ""

    def to_plain(self) -> dict:
        return {
            "formula_id": self.formula_id,
            "output_key": self.output_key,
            "tolerance": self.tolerance,
            "description": self.description,
        }


class FormulaReconciliationEngine:
    """注册与执行公式对账。"""

    def __init__(self) -> None:
        self._rules: dict[str, ReconciliationRule] = {}

    def register(self, rule: ReconciliationRule) -> None:
        self._rules[rule.formula_id] = rule

    def reconcile(
        self,
        stage_output: dict,
    ) -> list[dict]:
        """对给定 stage output 执行全部适用规则。

        stage_output 需含 `recompute_inputs` 字段（orchestrator 记录）。
        返回每个规则的对账结果。
        """
        inputs = stage_output.get("recompute_inputs", {})
        results = []
        for fid, rule in self._rules.items():
            recorded = stage_output.get(rule.output_key)
            if recorded is None:
                results.append({
                    "formula_id": fid, "output_key": rule.output_key,
                    "recorded": None, "recomputed": None,
                    "passed": False, "reason": "无记录输出",
                })
                continue
            try:
                recomputed = rule.recompute_fn(inputs)
                passed = _close(recorded, recomputed, rule.tolerance)
                results.append({
                    "formula_id": fid, "output_key": rule.output_key,
                    "recorded": recorded, "recomputed": recomputed,
                    "abs_diff": _abs_diff(recorded, recomputed),
                    "passed": passed,
                })
            except Exception as e:  # noqa: BLE001
                results.append({
                    "formula_id": fid, "output_key": rule.output_key,
                    "recorded": recorded, "recomputed": None,
                    "passed": False, "reason": f"重算失败: {e}",
                })
        return results

    def all_rules_pass(self, stage_output: dict) -> bool:
        return all(r["passed"] for r in self.reconcile(stage_output))


def _close(a: float, b: float, tol: float) -> bool:
    return abs(float(a) - float(b)) <= tol


def _abs_diff(a: float, b: float) -> float:
    return abs(float(a) - float(b))


# ---------------------------------------------------------------------------
# 预注册：VALOR 核心公式的独立重算（纯公式实现）
# ---------------------------------------------------------------------------
def build_valor_engine() -> FormulaReconciliationEngine:
    """注册 VALOR 全部核心公式对账规则。"""
    eng = FormulaReconciliationEngine()

    # ---- G9 Data-VOI：U_b = N_b Σ P̂(y,ŷ) r_{y,ŷ} ----
    def _recompute_data_voi(inp: dict) -> float:
        confusion = np.asarray(inp["confusion_matrix"], dtype=float)  # (ncls,ncls)
        payoff = np.asarray(inp["payoff_matrix"], dtype=float)
        n = float(np.sum(confusion))
        joint = confusion / n if n > 0 else confusion
        return float(inp["deployment_scale"]) * float(np.sum(joint * payoff))

    eng.register(ReconciliationRule(
        formula_id="DATA_VOI_UTILITY", output_key="u_plus",
        recompute_fn=_recompute_data_voi,
        description="U_b(θ)=N_b Σ P̂(y,ŷ) r_{y,ŷ}"))

    # ---- G6 audit cost：MC_A^pay == Σ 实际 VCG 支付 ----
    def _recompute_vcg_total(inp: dict) -> float:
        return float(sum(inp["vcg_payments"].values()))

    eng.register(ReconciliationRule(
        formula_id="MC_A_PAY", output_key="mc_a_pay",
        recompute_fn=_recompute_vcg_total,
        description="MC_A^pay = Σ 实际 VCG 支付"))

    # ---- G18 P_max：max{0, min[W_B^rem, V̲-C_I-C_{A,B}^pay-C_R^pay-C_{B,use}^cap-R_B^post]} ----
    def _recompute_pmax(inp: dict) -> float:
        val = (inp["v_gross_lower"] - inp["c_i"] - inp["c_a_b_pay"]
               - inp["c_r_pay"] - inp["c_b_use_cap"] - inp["r_b_post"])
        return max(0.0, min(inp["w_b_rem"], val))

    eng.register(ReconciliationRule(
        formula_id="PMAX", output_key="p_max", recompute_fn=_recompute_pmax,
        description="P_max = max{0, min[W_B^rem, V̲-...-R_B^post]}"))

    # ---- G19 P_min：c^marg+C_{A,S}^pay+C_B^cap+C_{R,S}^pay+R_S^post+OC_S+Π_S^0 ----
    def _recompute_pmin(inp: dict) -> float:
        return (inp["c_marg"] + inp["c_a_s_pay"] + inp["c_b_cap"]
                + inp["c_r_s_pay"] + inp["r_s_post"] + inp["oc_s"] + inp["pi_s0"])

    eng.register(ReconciliationRule(
        formula_id="PMIN", output_key="p_min", recompute_fn=_recompute_pmin,
        description="P_min = c^marg+C_{A,S}^pay+C_B^cap+...+Π_S^0"))

    # ---- G20 Clearing：M_T=P_max-P_min；P*=P_min+β_bar·M_T ----
    def _recompute_clearing(inp: dict) -> float:
        margin = inp["p_max"] - inp["p_min"]
        if margin < 0:
            return float("nan")  # NO_TRADE
        return inp["p_min"] + inp["beta_bar"] * margin

    eng.register(ReconciliationRule(
        formula_id="CLEAR_TRADE", output_key="clearing_price",
        recompute_fn=_recompute_clearing,
        description="P* = P_min + β_bar·(P_max-P_min)"))

    # ---- G16 p̲_B^sys：Q_{α_D}[Beta(a_D+TP, b_D+FN)] ----
    def _recompute_p_breach(inp: dict) -> float:
        from scipy.stats import beta

        a = inp["a_D"] + inp["tp"]
        b = inp["b_D"] + inp["fn"]
        return float(beta.ppf(inp["alpha_D"], a, b))

    eng.register(ReconciliationRule(
        formula_id="P_BREACH_LOWER_SYS", output_key="p_breach_lower_sys",
        recompute_fn=_recompute_p_breach,
        description="p̲_B^sys = Q_{α_D}[Beta(a_D+TP, b_D+FN)]"))

    return eng


__all__ = [
    "ReconciliationRule", "FormulaReconciliationEngine", "build_valor_engine",
]
