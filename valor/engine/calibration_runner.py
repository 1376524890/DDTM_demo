"""离线校准运行器（P6）—— 受控 breach injection → 检测 → TP/FN → 冻结 artifact。

流程（对齐交接文档第十节）：
    Historical Calibration Pool
        → 受控 breach injection（missingness / duplicate 等）
        → 运行检测 primitive → DetectionStats(TP/FP/FN/TN)
        → AuditLikelihoodCalibrator：由 sensitivity/FPR 派生 Λ_j
        → AuditPolicyCertifier：由 TP/FN 计算 Beta 下界 → 冻结 p̲_B^sys
    同时用 pseudo-historical 交易 residual 校准 V̲ 下界。

产出 CalibrationBundle 并写入 artifacts 目录，在线交易 manifest 引用其 hash。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from valor.core.hashing import content_hash
from valor.engine.artifacts import RunArtifacts
from valor.engine.calibration import (
    AuditLikelihoodCalibrator,
    AuditPolicyCertifier,
    CalibrationBundle,
    DetectionStats,
    FrozenArtifact,
    ValuationCalibrator,
)


@dataclass
class CalibrationConfig:
    """离线校准配置。"""

    historical_pool: pd.DataFrame  # Historical Calibration Pool
    breach_family: str = "structural"
    alpha_v: float = 0.1  # V̲ 下界置信分位数
    a_D: float = 1.0
    b_D: float = 1.0
    alpha_D: float = 0.05
    policy_hash: str = "p" * 64
    action_catalog_hash: str = "a" * 64
    dataset_hash: str = "d" * 64
    trainer_hash: str = "t" * 64
    buyer_context_family: str = "digit-classification"
    seed: int = 0
    # 注入比例（受控，非拍脑袋）
    missingness_fraction: float = 0.1
    duplicate_fraction: float = 0.05


def _inject_missingness(df: pd.DataFrame, frac: float, seed: int) -> pd.DataFrame:
    """受控 missingness 注入（§15.4）。"""
    rng = np.random.default_rng(seed)
    out = df.copy()
    n = len(out)
    n_miss = int(round(frac * n))
    rows = rng.choice(n, size=n_miss, replace=False)
    for r in rows:
        col = out.columns[rng.integers(0, len(out.columns))]
        out.iloc[r, out.columns.get_loc(col)] = np.nan
    return out


def _inject_duplicates(df: pd.DataFrame, frac: float, seed: int) -> pd.DataFrame:
    """受控整行重复注入（§15.4 exact_duplicate）。"""
    rng = np.random.default_rng(seed)
    out = df.copy()
    n = len(out)
    n_dup = int(round(frac * n))
    for _ in range(n_dup):
        src = rng.integers(0, n)
        out = pd.concat([out, out.iloc[[src]]], ignore_index=True)
    return out


def _detect_structural(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """运行 structural 检测，返回 (detected 布尔数组, error_rows 布尔数组)。

    用 duplicate_rate 检测整行重复（exact_duplicate 注入，不引入 NaN，structural
    的 row-hash 可正常处理）。检测到的重复行标记为 True。
    """
    from valor.quality.native.duplicates import run_exact_duplicates

    out = run_exact_duplicates(df)
    n = len(df)
    detected = np.zeros(n, dtype=bool)
    for r in out.detail.get("duplicate_indices", []):
        if isinstance(r, (int, np.integer)) and 0 <= int(r) < n:
            detected[int(r)] = True
    return detected, None


def run_offline_calibration(
    config: CalibrationConfig,
    *,
    run_dir: str | Path = "calibration",
    run_id: str | None = None,
) -> CalibrationBundle:
    """执行离线校准，写入 artifacts，返回冻结 bundle。"""
    from valor.core.ids import new_id

    run_id = run_id or new_id("calib", entropy=10)
    arts = RunArtifacts(Path(run_dir) / run_id, run_id=run_id)

    df = config.historical_pool

    # ---- 1. 估值校准：pseudo-historical residuals ----
    vc = ValuationCalibrator(alpha_v=config.alpha_v)
    # 伪历史：用不同 seed 重采样子池作为"历史交易"，V̂ 与 V^real 有已知偏差
    rng = np.random.default_rng(config.seed)
    n = len(df)
    for k in range(5):
        sub = df.iloc[rng.integers(0, n, size=max(50, n // 3))]
        predicted = float(len(sub))  # 简化代理量（演示用）
        realized = predicted * (1 + rng.normal(0, 0.05))
        vc.add(realized, predicted)
    valuation_art = vc.freeze(
        dataset_hash=config.dataset_hash, trainer_hash=config.trainer_hash,
        buyer_context_family=config.buyer_context_family, seed=config.seed)

    # ---- 2. 受控 breach injection → 检测 TP/FN ----
    # 用 exact_duplicate 注入（不引入 NaN，structural/duplicate 可处理）
    clean = df.reset_index(drop=True)
    n_clean = len(clean)
    n_dup = int(round(config.duplicate_fraction * n_clean))
    inj_dup = clean.copy()
    rng = np.random.default_rng(config.seed)
    dup_source = rng.integers(0, n_clean, size=n_dup)
    for s in dup_source:
        inj_dup = pd.concat([inj_dup, inj_dup.iloc[[int(s)]]], ignore_index=True)
    # positive：真实重复行 = 原 clean 中被复制源行 + 追加的重复行（简化：追加行）
    n_total = len(inj_dup)
    positive = np.zeros(n_total, dtype=bool)
    positive[n_clean:] = True  # 追加的重复行是 breach
    detected_arr = _detect_structural(inj_dup)[0]
    tp = int(np.sum(detected_arr & positive))
    fp = int(np.sum(detected_arr & ~positive))
    fn = int(np.sum(~detected_arr & positive))
    tn = int(np.sum(~detected_arr & ~positive))
    det_stats = DetectionStats(tp=tp, fp=fp, fn=fn, tn=tn)

    lik_cal = AuditLikelihoodCalibrator(
        action_id="a1", breach_family=config.breach_family,
        prior_state_probs={"G": 0.6, "L": 0.2, "B": 0.2})
    likelihood_art = lik_cal.freeze(det=det_stats, policy_hash=config.policy_hash)

    certifier = AuditPolicyCertifier(a_D=config.a_D, b_D=config.b_D,
                                     alpha_D=config.alpha_D)
    certificate_art = certifier.certify(
        cell_id="c1", breach_family=config.breach_family, tp=tp, fn=fn,
        policy_hash=config.policy_hash,
        action_catalog_hash=config.action_catalog_hash)

    bundle = CalibrationBundle(valuation=valuation_art,
                               likelihood=likelihood_art,
                               certificate=certificate_art)

    # ---- 3. 落盘 ----
    arts.write_manifest({
        "run_id": run_id,
        "kind": "calibration",
        "dataset_hash": config.dataset_hash,
        "trainer_hash": config.trainer_hash,
        "hashes": bundle.hashes(),
    })
    arts.write_json("calibration_bundle.json", bundle.to_plain())
    return bundle


__all__ = ["CalibrationConfig", "run_offline_calibration"]
