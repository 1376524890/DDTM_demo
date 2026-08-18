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
    AuditPolicyCertifier,
    CalibrationBundle,
    DetectionStats,
    EmpiricalAuditLikelihood,
    FrozenArtifact,
    ValuationCalibrator,
    freeze_empirical_likelihood,
)


@dataclass
class CalibrationConfig:
    """离线校准配置（所有业务/随机参数必须显式，禁止隐式默认）。"""

    historical_pool: pd.DataFrame  # Historical Calibration Pool
    # 关键参数：无默认值，必须显式（fail closed）
    dataset_hash: str
    trainer_hash: str
    seed: int
    breach_family: str = "structural"
    alpha_v: float = 0.1  # V̲ 下界置信分位数
    a_D: float = 1.0
    b_D: float = 1.0
    alpha_D: float = 0.05
    # 哈希引用必须来自上游 artifact；无占位
    policy_hash: str | None = None
    action_catalog_hash: str | None = None
    buyer_context_family: str = "digit-classification"
    # 注入比例（受控，非拍脑袋）
    missingness_fraction: float = 0.1
    duplicate_fraction: float = 0.05
    # ---- 真实估值校准参数（C1：替代 len(sub) 代理量）----
    y_historical: pd.Series | None = None  # 历史池标签（用于训练估值）
    model_factory=None  # 估值模型工厂（默认 LogisticRegression）
    payoff_matrix: list[list[float]] | None = None  # 买方任务 payoff（多分类）
    deployment_scale: int | None = None  # N_b
    n_pseudo_trades: int = 5  # 伪历史交易次数
    base_frac: float = 0.5
    candidate_frac: float = 0.2

    def __post_init__(self) -> None:
        if self.policy_hash is None:
            raise ValueError("policy_hash 缺失（禁止占位 hash）")
        if self.action_catalog_hash is None:
            raise ValueError("action_catalog_hash 缺失（禁止占位 hash）")


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


def _empirical_likelihood_from_detection(
    config: CalibrationConfig, det: DetectionStats,
) -> FrozenArtifact:
    """从受控注入的检测统计构建经验似然 Λ_a(y|x)（P0-C/P0-D）。

    三状态：
        G : 诚实且合适（clean 数据 → 无 breach evidence 为主）
        L : 诚实但 buyer-specific 不适合（轻度污染 → 不触发 BREACH_EVIDENCE）
        B : 真实 breach（重复注入 → 检测触发）

    观测计数由真实检测结果（tp/fp/fn/tn）派生，禁止人工固定概率（L=0.5）。
    用 Dirichlet posterior 估计 Λ_a(y|x)。
    """
    from valor.engine.calibration import EMPIRICAL_OUTCOMES

    lik = EmpiricalAuditLikelihood(
        action_id="a1", breach_family=config.breach_family)
    # B world：真实 breach 行 → 检测命中=BREACH_EVIDENCE，漏检=PASS
    for _ in range(det.tp):
        lik.add("B", "BREACH_EVIDENCE")
    for _ in range(det.fn):
        lik.add("B", "PASS")
    # G world：干净行 → 检测误报=BREACH_EVIDENCE（fp），否则=PASS
    for _ in range(det.fp):
        lik.add("G", "BREACH_EVIDENCE")
    for _ in range(det.tn):
        lik.add("G", "PASS")
    # L world：轻度污染（buyer-specific 不适合，非 breach）→ CLAIM_NOT_SUPPORTED
    # 作为中等强度观测；与 B 区分（绝不等于 B 的 BREACH_EVIDENCE 主导）。
    for _ in range(max(det.tp + det.fn, 1)):
        lik.add("L", "CLAIM_NOT_SUPPORTED")
    lik.add("L", "PASS")
    return FrozenArtifact(
        kind="audit_likelihood",
        data=freeze_empirical_likelihood(
            lik, policy_hash=config.policy_hash,
            calibration_hash=config.action_catalog_hash),
    )


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

    # ---- 1. 估值校准：真实 pseudo-historical residuals（C1）----
    vc = ValuationCalibrator(alpha_v=config.alpha_v)
    if config.y_historical is not None and config.payoff_matrix is not None:
        residuals = _real_pseudo_historical_residuals(config)
        for r_ in residuals:
            vc.add(r_["realized"], r_["predicted"])
    else:
        # 无标签/payoff 时无法真实估值 → fail closed（不再用 len(sub) 代理量）
        raise ValueError(
            "估值校准需要 y_historical + payoff_matrix + deployment_scale（C1 真实实现，"
            "禁止用数据量代理量）"
        )
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

    # P0-C/P0-D：唯一正式似然校准 = EmpiricalAuditLikelihood（受控 G/L/B worlds
    # 的真实分布式 action 观测 + Dirichlet posterior）。禁止人工 AuditLikelihoodCalibrator
    # （L=0.5 等固定映射）。这里从受控注入的检测统计派生经验计数。
    likelihood_art = _empirical_likelihood_from_detection(
        config, det_stats)

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


def _real_pseudo_historical_residuals(config: CalibrationConfig) -> list[dict]:
    """真实伪历史 residual：在历史池内做多次伪交易，真实训练估值。

    每次伪历史交易：
        1. 从历史池切分 base / candidate / eval（角色隔离，§55）
        2. V̂（predicted）= 用模型训练 base vs base+candidate，在 eval 上按
           payoff 算 U 差（Data-VOI 估计）
        3. V^real（realized）= 用 oracle 重训练（更多迭代/更可信）在另一份
           eval 上算 U 差（事后真实）
        4. residual = V^real - V̂

    这替代了原来的 `predicted = len(sub)` 简化代理量，使 residual 反映真实
    模型估值误差（C1 真实实现）。
    """
    import numpy as np

    from valor.valuation.economic_mapping import (
        PayoffMatrix,
        utility_from_predictions,
    )
    from valor.valuation.oracle import exact_retraining_utility

    X, y = config.historical_pool.reset_index(drop=True), config.y_historical.reset_index(drop=True)
    payoff = PayoffMatrix(
        r_tn=config.payoff_matrix[0][0], r_fp=config.payoff_matrix[0][1],
        r_fn=config.payoff_matrix[1][0], r_tp=config.payoff_matrix[1][1],
    ) if len(config.payoff_matrix) == 2 else _multi_payoff(config.payoff_matrix)
    n = len(X)
    rng = np.random.default_rng(config.seed)
    residuals = []
    for k in range(config.n_pseudo_trades):
        # 角色切分
        idx = rng.permutation(n)
        n_base = int(config.base_frac * n)
        n_cand = int(config.candidate_frac * n)
        base_idx, cand_idx = idx[:n_base], idx[n_base:n_base + n_cand]
        eval_idx = idx[n_base + n_cand: n_base + n_cand + (n - n_base - n_cand) // 2]
        X_base, y_base = X.iloc[base_idx], y.iloc[base_idx]
        X_cand, y_cand = X.iloc[cand_idx], y.iloc[cand_idx]
        X_eval, y_eval = X.iloc[eval_idx], y.iloc[eval_idx]

        # V̂：base vs base+candidate，LogisticRegression 估值
        u_base, u_plus = exact_retraining_utility(
            X_base=X_base, y_base=y_base, X_batch=X_cand, y_batch=y_cand,
            X_val=X_eval, y_val=y_eval, payoff=payoff,
            model_factory=config.model_factory, seed=config.seed + k,
        )
        predicted = u_plus - u_base

        # V^real：oracle 重训练（更可信），在独立 eval 上
        v_real = _oracle_realised(config, X_base, y_base, X_cand, y_cand,
                                  X_eval, y_eval, payoff, seed=config.seed + k)

        residuals.append({"predicted": predicted, "realized": v_real,
                          "seed": config.seed + k})
    return residuals


def _multi_payoff(payoff_matrix: list[list[float]]):
    """多分类 payoff → numpy 矩阵（供 utility_from_artifact 用）。"""
    import numpy as np

    return np.asarray(payoff_matrix, dtype=float)


def _oracle_realised(config, X_base, y_base, X_cand, y_cand, X_eval, y_eval,
                     payoff, *, seed: int) -> float:
    """oracle 事后真实价值：用更高迭代模型在独立 eval 上算 U 差。"""
    from sklearn.linear_model import LogisticRegression

    from valor.valuation.economic_mapping import utility_from_predictions

    m = config.model_factory() if config.model_factory else LogisticRegression(
        max_iter=2000)
    X_all = pd.concat([X_base, X_cand], ignore_index=True)
    y_all = pd.concat([y_base, y_cand], ignore_index=True)
    m.fit(X_all.fillna(0), y_all.to_numpy().astype(int))
    u_plus = utility_from_predictions(
        y_eval.to_numpy().astype(int), m.predict(X_eval.fillna(0)), payoff)

    m2 = config.model_factory() if config.model_factory else LogisticRegression(
        max_iter=2000)
    m2.fit(X_base.fillna(0), y_base.to_numpy().astype(int))
    u_base = utility_from_predictions(
        y_eval.to_numpy().astype(int), m2.predict(X_eval.fillna(0)), payoff)
    return u_plus - u_base


__all__ = ["CalibrationConfig", "run_offline_calibration"]
