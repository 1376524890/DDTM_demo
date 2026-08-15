"""RQ 实验框架（P13，交接文档 Level 1-4 + 第二十二节统计规范）。

Level 1  Mathematical Reconciliation：验证每个公式（code result == 独立重算）
Level 2  Mechanism Integration：验证模块接线（上游输出成为下游真实输入）
Level 3  Capstone Full Transaction：固定 MNIST 场景跑通
Level 4  Scientific RQ：多 seed paired trials + 统计

统一统计规范：multiple seeds / paired trials / mean-median-std-95%CI /
paired t-test 或 Wilcoxon / effect size / Holm correction。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from valor.evaluation.statistics import holm_correction, mean_ci, paired_test
from valor.engine.orchestrator import OrchestrationResult, run_capstone
from valor.engine.scenario import CapstoneScenario


# ---------------------------------------------------------------------------
# Level 1: 数学对账
# ---------------------------------------------------------------------------
@dataclass
class ReconciliationCase:
    """一个公式对账用例：code 计算 vs 独立重算。"""

    name: str
    compute: Callable[[], float]
    recompute: Callable[[], float]
    tolerance: float = 1e-9

    def run(self) -> dict:
        code = self.compute()
        indep = self.recompute()
        return {
            "name": self.name,
            "code": code, "independent": indep,
            "abs_diff": abs(code - indep),
            "passed": abs(code - indep) <= self.tolerance,
        }


def level1_reconciliation() -> list[dict]:
    """Level 1：核心公式独立重算对账。"""
    from valor.liability.seller_bond import reconcile_seller_bond, seller_bond_required
    from valor.pricing.buyer_max import buyer_max_price
    from valor.pricing.seller_min import seller_min_price
    from valor.audit.voi import marginal_value_of_audit

    cases = [
        ReconciliationCase(
            "seller_bond_B_star",
            lambda: seller_bond_required(p_breach_lower_sys=0.8, g_dev=60, eps_s=1,
                                         p_e_bond=1, p_e_f=0.3, lambda_s=0.5, f_s=10),
            lambda: max(0.0, ((60 + 1) / 0.8 - 0.3 * 10) / (1.0 * 0.5)),
        ),
        ReconciliationCase(
            "buyer_max_price",
            lambda: buyer_max_price(w_b_rem=500, v_gross_lower=300, c_i=20,
                                    c_a_b_pay=10, c_r_pay=5, c_b_use_cap=2, r_b_post=5),
            lambda: max(0.0, min(500, 300 - 20 - 10 - 5 - 2 - 5)),
        ),
        ReconciliationCase(
            "seller_min_price",
            lambda: seller_min_price(c_marg=5, c_a_s_pay=10, c_b_cap=15,
                                     c_r_s_pay=3, r_s_post=4, oc_s=6, pi_s0=10),
            lambda: 5 + 10 + 15 + 3 + 4 + 6 + 10,
        ),
        ReconciliationCase(
            "bond_IC_slack",
            lambda: reconcile_seller_bond(
                bond=seller_bond_required(p_breach_lower_sys=0.8, g_dev=60, eps_s=1,
                                          p_e_bond=1, p_e_f=0.3, lambda_s=0.5, f_s=10),
                p_breach_lower_sys=0.8, g_dev=60, eps_s=1, p_e_bond=1,
                p_e_f=0.3, lambda_s=0.5, f_s=10)["constraint_slack"],
            lambda: 0.8 * (1.0 * 0.5 * max(0.0, ((61) / 0.8 - 3) / 0.5) + 0.3 * 10) - 61,
            tolerance=1e-6,
        ),
    ]
    return [c.run() for c in cases]


# ---------------------------------------------------------------------------
# Level 4: 统计实验
# ---------------------------------------------------------------------------
@dataclass
class ExperimentTrial:
    """一次实验 trial。"""

    trial_id: str
    seed: int
    params: dict[str, Any]
    result: OrchestrationResult | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    error: str | None = None

    def to_plain(self) -> dict:
        return {
            "trial_id": self.trial_id, "seed": self.seed, "params": self.params,
            "decision": self.result.decision if self.result else None,
            "terminal_state": self.result.terminal_state if self.result else None,
            "clearing_price": self.result.clearing_price if self.result else None,
            "metrics": self.metrics, "error": self.error,
        }


@dataclass
class ExperimentGroup:
    """一组同场景多 seed trials。"""

    name: str
    trials: list[ExperimentTrial] = field(default_factory=list)

    def metric_values(self, metric: str) -> np.ndarray:
        vals = [t.metrics.get(metric, np.nan) for t in self.trials
                if t.result is not None and metric in t.metrics]
        return np.asarray([v for v in vals if not np.isnan(v)], dtype=float)

    def summarize(self, metric: str) -> dict:
        x = self.metric_values(metric)
        if len(x) == 0:
            return {"metric": metric, "n": 0}
        m, lo, hi = mean_ci(x)
        return {
            "metric": metric, "n": len(x),
            "mean": m, "median": float(np.median(x)),
            "std": float(np.std(x, ddof=1)) if len(x) > 1 else 0.0,
            "ci_lower": lo, "ci_upper": hi,
        }

    def to_plain(self) -> dict:
        return {
            "name": self.name,
            "n_trials": len(self.trials),
            "trials": [t.to_plain() for t in self.trials],
        }


class ExperimentRunner:
    """多 seed paired-trials 实验运行器（Level 4）。"""

    def __init__(
        self,
        *,
        scenario_factory: Callable[[dict], CapstoneScenario],
        n_seeds: int = 30,
        run_dir: str | Path = "runs/experiments",
        calibration=None,
        metric_fn: Callable[[OrchestrationResult], dict[str, float]] | None = None,
    ) -> None:
        self.scenario_factory = scenario_factory
        self.n_seeds = n_seeds
        self.run_dir = run_dir
        self.calibration = calibration
        self.metric_fn = metric_fn or (lambda res: {
            "clearing_price": res.clearing_price or 0.0,
        })

    def run_group(self, name: str, param_overrides: dict | None = None) -> ExperimentGroup:
        group = ExperimentGroup(name=name)
        for seed in range(self.n_seeds):
            sc = self.scenario_factory(param_overrides or {})
            sc.split_seed = seed
            sc.scenario_id = f"{name}-{seed}"
            trial = ExperimentTrial(trial_id=f"{name}-{seed}", seed=seed,
                                    params=param_overrides or {})
            try:
                res = run_capstone(sc, run_dir=self.run_dir,
                                   calibration=self.calibration)
                trial.result = res
                trial.metrics = self.metric_fn(res)
            except Exception as e:  # noqa: BLE001
                trial.error = str(e)
            group.trials.append(trial)
        return group


def compare_groups(
    groups: dict[str, ExperimentGroup],
    metric: str,
    baseline: str | None = None,
) -> dict:
    """比较多组同一 metric；baseline 组作对照，多 baseline 用 Holm 校正。"""
    base_name = baseline or list(groups)[0]
    base_vals = groups[base_name].metric_values(metric)
    result: dict[str, Any] = {}
    pvals = []
    names = []
    for name, grp in groups.items():
        if name == base_name:
            continue
        vals = grp.metric_values(metric)
        test = paired_test(base_vals, vals) if len(base_vals) == len(vals) else {
            "method": "unpaired", "p": 1.0}
        # effect size (Cohen's d)
        if len(vals) > 1 and len(base_vals) > 1:
            pooled = np.sqrt((np.std(vals, ddof=1) ** 2 + np.std(base_vals, ddof=1) ** 2) / 2)
            d = (np.mean(vals) - np.mean(base_vals)) / pooled if pooled > 0 else 0.0
        else:
            d = 0.0
        pvals.append(test["p"])
        names.append(name)
        result[name] = {"vs": base_name, **test, "effect_size": float(d)}
    # Holm correction（多组）
    if len(pvals) > 1:
        adj = holm_correction(pvals)
        for name, p in zip(names, adj):
            result[name]["p_holm"] = float(p)
    return {"baseline": base_name, "comparisons": result}


__all__ = [
    "ReconciliationCase", "level1_reconciliation",
    "ExperimentTrial", "ExperimentGroup", "ExperimentRunner", "compare_groups",
]
