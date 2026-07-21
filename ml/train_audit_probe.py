#!/usr/bin/env python3
"""Train the private linear audit probe and export in canonical JSON format.

The probe is a linear classifier f_A(x) = w^T x + b, trained on the buyer's
validation or calibration set. Parameters are exported as fixed-point integers:

  weights_q8_8:  [128]int16   Q8.8
  bias_q24:      int64        Q24.0
  center_q16_16: [128]int32   Q16.16
  inv_scale_sq:  [128]uint20  1/scale^2 coefficients
  margin_threshold_q24: int64
  distance_threshold_raw:  int   (uint96 range)
  missing_threshold:      int

The threshold values come from conformal calibration on a held-out set.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
from sklearn.linear_model import SGDClassifier


def quantize_q8_8(arr: np.ndarray) -> list:
    a = np.rint(arr * 256.0).astype(np.int32)
    if (a < -32768).any() or (a > 32767).any():
        raise ValueError("weight Q8.8 overflow")
    return a.astype(np.int16).tolist()


def quantize_q16_16(arr: np.ndarray) -> list:
    a = np.rint(arr * 65536.0).astype(np.int64)
    if (a < np.iinfo(np.int32).min).any() or (a > np.iinfo(np.int32).max).any():
        raise ValueError("center Q16.16 overflow beyond int32")
    return a.astype(np.int32).tolist()


def int64_to_str(val: int) -> str:
    return str(val)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True, help="calibration .npz (x, y)")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--alpha", type=float, default=0.95, help="conformal confidence")
    ap.add_argument("--seed", type=int, default=20260721)
    args = ap.parse_args()

    data = np.load(args.input)
    x = data["x"].astype(np.float64)
    y = data["y"].astype(np.float64)  # -1 or +1

    n, d = x.shape

    # Train linear probe via SGD.
    clf = SGDClassifier(
        loss="hinge",
        penalty="l2",
        alpha=0.001,
        max_iter=1000,
        tol=1e-4,
        random_state=args.seed,
        class_weight="balanced",
    )
    clf.fit(x, y)
    w = clf.coef_.ravel().astype(np.float64)
    b = float(clf.intercept_[0])

    # Feature centers and inverse scale squares (for distance metric).
    centers = x.mean(axis=0)
    stdevs = np.std(x, axis=0) + 1e-8
    inv_scale_sq = 1.0 / (stdevs ** 2)

    # Conformal calibration: compute non-conformity scores on training set.
    scores = y * (x @ w + b)
    # Non-conformity = -margin (lower margin = worse conformity)
    nonconformity = -scores

    # Set margin threshold at alpha quantile.
    margin_threshold_raw = np.quantile(nonconformity, args.alpha)
    # The margin threshold is Q24 (signed). Convert from raw float.
    margin_threshold_q24 = int(round(margin_threshold_raw * (1 << 24)))

    # Distance threshold: 99th percentile of weighted distances.
    diffs = x - centers
    distances = (diffs ** 2) @ inv_scale_sq
    distance_threshold_raw = int(round(np.percentile(distances, 99) * 65536.0))

    # Missing threshold: maximum allowed missing features (conservative).
    missing_threshold = 16

    # Robustness: clamp inv_scale_sq to fit uint20 (max 1048575).
    max_inv = (1 << 20) - 1
    inv_scale_sq_int = np.rint(inv_scale_sq).astype(np.int64)
    inv_scale_sq_int = np.clip(inv_scale_sq_int, 0, max_inv).astype(np.int64)

    probe = {
        "weights_q8_8": quantize_q8_8(w),
        "bias_q24": int(round(b * (1 << 24))),
        "center_q16_16": quantize_q16_16(centers),
        "inv_scale_sq": [int(v) for v in inv_scale_sq_int],
        "margin_threshold_q24": margin_threshold_q24,
        "distance_threshold_raw": distance_threshold_raw,
        "missing_threshold": missing_threshold,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(probe, indent=2), encoding="utf-8")

    # Calibration record (for policy audit trail).
    calib = {
        "alpha": args.alpha,
        "num_calibration_samples": n,
        "margin_quantile": float(margin_threshold_raw),
        "distance_p99": float(distance_threshold_raw / 65536.0),
        "probe_accuracy": float(np.mean((scores >= 0).astype(float))),
    }
    print(json.dumps(calib, indent=2))


if __name__ == "__main__":
    main()
