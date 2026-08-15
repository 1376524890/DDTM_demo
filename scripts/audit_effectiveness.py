"""MNIST 审计效果对比实验（脚本）。

回答：零知识审计 vs 常规训练 baseline，审计是否真的检测出 MNIST 数据质量问题？

设计：
  1. 常规训练 baseline：直接在 (base + candidate) 上训练 MLP，在 FinalEvaluation 测精度。
     - 干净 candidate  → 精度高
     - 污染 candidate（covariate shift / label 污染）→ 精度下降（买方事后才察觉）
  2. 零知识审计：在交易前对 candidate 运行质量 primitive（不接触 FinalEvaluation）：
     - 用 reference（历史池）与 candidate 做分布漂移检测（MMD / KS）
     - 用 confident_learning 检测 label 污染
     - 干净 candidate  → PASS；污染 candidate → QUALITY_FAIL / BREACH_EVIDENCE

结论：若审计在训练前就标记污染 candidate（PASS 区分干净/污染），而 baseline 只能
事后通过精度下降察觉，则证明审计确实有效（早于/独立于训练）。

用法：
  python scripts/audit_effectiveness.py [--samples 4000] [--shift 40] [--label-flip 0.1]
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from valor.data.download import load_dataset


# ---------------------------------------------------------------------------
# 数据准备
# ---------------------------------------------------------------------------
def _prepare(seed: int = 0, n_cand: int = 4000):
    """加载 MNIST，分出 base / candidate / reference / final（角色隔离）。"""
    h = load_dataset("mnist")
    X, y = h.X, h.y
    rng = np.random.default_rng(seed)
    n = len(X)
    perm = rng.permutation(n)
    base_idx = perm[:20000]
    ref_idx = perm[20000:25000]           # 历史校准池（reference）
    cand_idx = perm[25000:25000 + n_cand]  # 卖方候选
    final_idx = perm[30000:]               # FinalEvaluation
    return {
        "base": (X.iloc[base_idx], y.iloc[base_idx]),
        "reference": (X.iloc[ref_idx], y.iloc[ref_idx]),
        "candidate": (X.iloc[cand_idx], y.iloc[cand_idx]),
        "final": (X.iloc[final_idx], y.iloc[final_idx]),
    }


def _corrupt_covariate(cand, frac: float = 1.0, shift: float = 40.0, seed: int = 1):
    """covariate shift 污染：对候选部分样本像素整体加偏移（模拟采集漂移）。"""
    X, y = cand
    X = X.astype(float).copy()
    rng = np.random.default_rng(seed)
    n = len(X)
    idx = np.arange(n) if frac >= 1.0 else rng.choice(n, size=int(frac * n), replace=False)
    X.iloc[idx] = X.iloc[idx] + shift  # 整行像素漂移
    X = X.clip(0, 255)
    return X, y


def _corrupt_labels(cand, frac: float = 0.1, seed: int = 2):
    """label 污染：随机改 label 为错误类（模拟标注错误）。"""
    X, y = cand
    y = y.copy()
    rng = np.random.default_rng(seed)
    n = len(y)
    idx = rng.choice(n, size=int(frac * n), replace=False)
    for i in idx:
        wrong = rng.choice([c for c in range(10) if c != y.iloc[i]])
        y.iloc[i] = wrong
    return X, y


# ---------------------------------------------------------------------------
# 常规训练 baseline
# ---------------------------------------------------------------------------
def _train_acc(base, cand, final, *, epochs=2, batch_size=256, seed=0):
    """在 base+candidate 上训练 MLP，FinalEvaluation 测精度。"""
    from valor.valuation.mnist_trainer import train_mnist_mlp

    Xb, yb = base
    Xc, yc = cand
    Xf, yf = final
    X_all = pd.concat([Xb, Xc], ignore_index=True)
    y_all = pd.concat([yb, yc], ignore_index=True)
    res = train_mnist_mlp(
        X_all, y_all, Xf, yf, epochs=epochs, batch_size=batch_size, seed=seed,
        max_samples=len(X_all),
    )
    return res["test_acc"]


# ---------------------------------------------------------------------------
# 零知识审计（交易前，质量 primitive）
# ---------------------------------------------------------------------------
def _audit_quality(reference, candidate, *, seed=0):
    """在交易前对 candidate 运行质量检测，返回 (outcome, metrics)。

    用 reference（历史池）作为基线分布，检测 candidate 是否漂移/污染。
    """
    from valor.quality.native.ks_shift import run_ks_shift

    X_ref, _ = reference
    X_cand, y_cand = candidate

    # KS 分布漂移检测（在代表性像素列上，MNIST 用像素均值/方差压缩）
    # 784 维逐列 KS 太慢 → 用每行统计量（均值/标准差/稀疏度）作为检测特征
    ref_feat = _row_features(X_ref)
    cand_feat = _row_features(X_cand)

    # 用 KS 检测特征分布漂移
    from scipy.stats import ks_2samp

    drift_metrics = {}
    max_p = 0.0
    min_p = 1.0
    for col in ref_feat.columns:
        ks = ks_2samp(ref_feat[col], cand_feat[col])
        drift_metrics[col] = {
            "statistic": float(ks.statistic), "pvalue": float(ks.pvalue),
        }
        max_p = max(max_p, ks.pvalue)
        min_p = min(min_p, ks.pvalue)

    # 判定：任一特征显著漂移（p 很小）→ 数据质量问题
    alpha = 0.01
    n_sig = sum(1 for m in drift_metrics.values() if m["pvalue"] < alpha)

    # confident_learning label 污染检测（候选内部标注一致性）
    label_metrics = _detect_label_issues(X_cand, y_cand, seed=seed)

    # 综合判定：分布漂移 或 候选内部 label 误差率显著高 → QUALITY_FAIL
    label_error = label_metrics.get("estimated_label_error_rate", 0.0)
    # 干净 MNIST 的 CL 基线误差率约 0.19（LR-OOF 固有）；污染时应显著更高
    label_flagged = label_error > 0.28  # 经验阈值，>干净基线 + 容差
    outcome = "QUALITY_FAIL" if (n_sig >= 1 or label_flagged) else "PASS"

    return {
        "outcome": outcome,
        "n_significant_features": n_sig,
        "total_features": len(drift_metrics),
        "min_pvalue": min_p,
        "drift_metrics": drift_metrics,
        "label_metrics": label_metrics,
        "label_flagged": label_flagged,
    }


def _row_features(X: pd.DataFrame, sample: int = 2000) -> pd.DataFrame:
    """把 784 维像素压成行级统计特征（均值/标准差/稀疏度），加速 KS。"""
    if len(X) > sample:
        X = X.iloc[:sample]
    arr = X.to_numpy(dtype=float)
    return pd.DataFrame({
        "pixel_mean": arr.mean(axis=1),
        "pixel_std": arr.std(axis=1),
        "sparsity": (arr < 128).mean(axis=1),  # 暗像素比例
    })


def _detect_label_issues(X, y, *, seed=0, sample=2000):
    """confident_learning label 污染检测（OOF 概率）。"""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_predict
        from valor.quality.native.confident_learning import run_confident_learning

        n = min(len(X), sample)
        Xs = X.iloc[:n].fillna(0)
        ys = y.iloc[:n]
        # 降维：像素均值压缩到 64 维加速（检测只需区分 label 一致性）
        Xp = _compress(Xs, 64)
        clf = LogisticRegression(max_iter=200)
        probs = cross_val_predict(clf, Xp, ys.to_numpy(), cv=2,
                                  method="predict_proba")
        out = run_confident_learning(Xp, ys, probabilities=probs)
        return {
            "estimated_label_error_rate": out.metrics["estimated_label_error_rate"],
            "issue_rate": out.metrics["issue_rate"],
            "n_issues": out.metrics["n_issues"],
        }
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def _compress(X: pd.DataFrame, dim: int = 64) -> pd.DataFrame:
    """像素分块均值压缩（784 → dim），保留判别信息加速。"""
    arr = X.to_numpy(dtype=float)
    n = arr.shape[0]
    blocks = np.array_split(np.arange(784), dim)
    out = np.zeros((n, dim))
    for j, b in enumerate(blocks):
        out[:, j] = arr[:, b].mean(axis=1)
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=4000)
    ap.add_argument("--shift", type=float, default=40.0)
    ap.add_argument("--label-flip", type=float, default=0.1)
    ap.add_argument("--epochs", type=int, default=2)
    args = ap.parse_args()

    print("加载 MNIST...")
    data = _prepare(n_cand=args.samples)
    base, reference = data["base"], data["reference"]
    cand_clean = data["candidate"]
    final = data["final"]

    print("\n[1] 常规训练 baseline（base + candidate → FinalEvaluation 精度）")
    acc_clean = _train_acc(base, cand_clean, final, epochs=args.epochs)
    print(f"    干净 candidate → 精度 = {acc_clean:.4f}")

    print("\n[2] 污染 candidate（covariate shift）")
    cand_shift = _corrupt_covariate(cand_clean, shift=args.shift)
    acc_shift = _train_acc(base, cand_shift, final, epochs=args.epochs)
    print(f"    训练后精度 = {acc_shift:.4f}（下降 {acc_clean - acc_shift:.4f}）")

    print("\n[3] 污染 candidate（label 污染）")
    cand_lbl = _corrupt_labels(cand_clean, frac=args.label_flip)
    acc_lbl = _train_acc(base, cand_lbl, final, epochs=args.epochs)
    print(f"    训练后精度 = {acc_lbl:.4f}（下降 {acc_clean - acc_lbl:.4f}）")

    print("\n[4] 零知识审计（交易前，质量 primitive，不接触 FinalEvaluation）")
    for name, cand in [("干净", cand_clean), ("covariate_shift", cand_shift),
                       ("label污染", cand_lbl)]:
        res = _audit_quality(reference, cand)
        print(f"    {name:18s} → outcome={res['outcome']:12s} "
              f"显著漂移特征={res['n_significant_features']}/{res['total_features']} "
              f"min_p={res['min_pvalue']:.2e} "
              f"label_error={res['label_metrics'].get('estimated_label_error_rate', 0):.4f}")

    print("\n=== 结论 ===")
    print(f"baseline：干净={acc_clean:.4f} vs shift={acc_shift:.4f} vs label={acc_lbl:.4f}")
    print("若审计在干净→PASS、污染→QUALITY_FAIL，则证明审计在训练前就检测出数据质量问题。")


if __name__ == "__main__":
    main()
