"""Analysis（EF-G09..G13）：paired metrics + bootstrap CI + significance + effect size + Holm。

从 immutable trial results 生成：
    metrics.csv / paired_differences.csv / confidence_intervals.csv /
    significance.csv / effect_sizes.csv
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from valor.evaluation.statistics import (
    bootstrap_ci,
    cohens_dz,
    descriptive_stats,
    holm_correction,
    paired_test,
    rank_biserial,
)

from .artifacts import ArtifactStore


@dataclass
class PairedAnalysis:
    """对一对 method（proposed vs baseline）分析一个 metric。"""

    metric: str
    proposed: list[float]
    baseline: list[float]

    def paired_differences(self) -> list[float]:
        return [p - b for p, b in zip(self.proposed, self.baseline)]

    def proposed_stats(self) -> dict:
        return descriptive_stats(self.proposed)

    def baseline_stats(self) -> dict:
        return descriptive_stats(self.baseline)

    def bootstrap_ci_proposed(self, **kw) -> tuple:
        return bootstrap_ci(self.proposed, **kw)

    def test(self) -> dict:
        return paired_test(self.proposed, self.baseline)

    def effect_size(self) -> dict:
        return {
            "cohens_dz": cohens_dz(self.proposed, self.baseline),
            "rank_biserial": rank_biserial(self.proposed, self.baseline),
        }


class AnalysisRunner:
    """从 trial results 生成分析表。"""

    def __init__(self, store: ArtifactStore, out_dir: str | Path) -> None:
        self.store = store
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def _group_by_world_method(self, trial_ids: list[str]) -> dict:
        """world_id -> {method_id: result}（按 world 配对）。"""
        groups: dict[str, dict[str, dict]] = {}
        for tid in trial_ids:
            if not self.store.exists(tid):
                continue
            res = self.store.read_result(tid)
            if not res.get("success"):
                continue
            w, m = res["world_id"], res["method_id"]
            groups.setdefault(w, {})[m] = res
        return groups

    def paired_metric_matrix(self, trial_ids: list[str], metric: str,
                             proposed: str, baseline: str) -> PairedAnalysis:
        """对每 world 取 (proposed, baseline) 的 metric 值，构造 paired 分析。"""
        groups = self._group_by_world_method(trial_ids)
        p_vals, b_vals = [], []
        for w, methods in groups.items():
            if proposed in methods and baseline in methods:
                p_vals.append(methods[proposed]["metrics"].get(metric, np.nan))
                b_vals.append(methods[baseline]["metrics"].get(metric, np.nan))
        p_vals = [x for x in p_vals if not (isinstance(x, float) and np.isnan(x))]
        b_vals = [x for x in b_vals if not (isinstance(x, float) and np.isnan(x))]
        return PairedAnalysis(metric=metric, proposed=p_vals, baseline=b_vals)

    def analyze_pair(self, trial_ids: list[str], metric: str,
                     proposed: str, baseline: str, *, n_boot: int = 2000) -> dict:
        """完整分析一个 (proposed, baseline, metric)。"""
        pa = self.paired_metric_matrix(trial_ids, metric, proposed, baseline)
        diff = pa.paired_differences()
        ci = bootstrap_ci(diff)
        test = pa.test()
        es = pa.effect_size()
        return {
            "metric": metric, "proposed": proposed, "baseline": baseline,
            "n_worlds": len(pa.proposed),
            "proposed_stats": pa.proposed_stats(),
            "baseline_stats": pa.baseline_stats(),
            "mean_paired_diff": float(np.mean(diff)) if diff else None,
            "diff_ci_95": list(ci),
            "test": test,
            "effect_size": es,
            "holm_adjusted_p": None,
        }

    def holm_adjust(self, results: list[dict]) -> list[dict]:
        """对多个分析结果的 p 值做 Holm 校正（EF-G13）。"""
        pvals = [r["test"]["p"] for r in results]
        adj = holm_correction(pvals)
        for r, p in zip(results, adj):
            r["holm_adjusted_p"] = p
        return results

    def write_csvs(self, results: list[dict]) -> None:
        with open(self.out_dir / "significance.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["metric", "proposed", "baseline", "n", "mean_diff",
                        "diff_ci_low", "diff_ci_high", "method", "p",
                        "holm_p", "cohens_dz", "rank_biserial"])
            for r in results:
                w.writerow([
                    r["metric"], r["proposed"], r["baseline"], r["n_worlds"],
                    r["mean_paired_diff"], r["diff_ci_95"][1],
                    r["diff_ci_95"][2], r["test"]["method"], r["test"]["p"],
                    r["holm_adjusted_p"], r["effect_size"]["cohens_dz"],
                    r["effect_size"]["rank_biserial"],
                ])


__all__ = ["PairedAnalysis", "AnalysisRunner"]
