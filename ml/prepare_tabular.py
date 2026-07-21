#!/usr/bin/env python3
"""Prepare a numeric tabular binary-classification dataset for DDTM-QAS.

Input is CSV/Parquet with one binary label column. Categorical variables must be
encoded before this step or selected via --one-hot. The script creates a buyer
base-training split, a private validation split, and a seller-candidate split.
The fitted preprocessing policy is exported and must be committed before seller
evaluation.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder


def round_even_q16(x: np.ndarray) -> np.ndarray:
    y = np.rint(x * 65536.0)  # IEEE round-to-nearest-even
    if np.any(y < np.iinfo(np.int32).min) or np.any(y > np.iinfo(np.int32).max):
        raise ValueError("Q16.16 overflow")
    return y.astype(np.int32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20260721)
    ap.add_argument("--max-rows", type=int, default=200000)
    ap.add_argument("--seller-rows", type=int, default=100000)
    ap.add_argument("--validation-rows", type=int, default=20000)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(args.input) if args.input.suffix.lower() in {".parquet", ".pq"} else pd.read_csv(args.input)
    if len(df) > args.max_rows:
        df = df.sample(args.max_rows, random_state=args.seed)
    y_raw = df.pop(args.label)
    labels = sorted(pd.unique(y_raw.dropna()))
    if len(labels) != 2:
        raise ValueError(f"binary label required, got {labels}")
    y = np.where(y_raw.to_numpy() == labels[1], 1, -1).astype(np.int8)

    # One-hot encode categoricals and preserve missing indicators.
    cat_cols = list(df.select_dtypes(exclude=[np.number]).columns)
    num_cols = [c for c in df.columns if c not in cat_cols]
    num = df[num_cols].astype(np.float64)
    num_missing = num.isna().to_numpy()
    medians = num.median(axis=0)
    num = num.fillna(medians)
    q01 = num.quantile(0.01)
    q99 = num.quantile(0.99)
    scale = (q99 - q01).replace(0, 1.0)
    num_norm = ((num - q01) / scale).clip(-4, 4).to_numpy(np.float32)

    if cat_cols:
        enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False, max_categories=16)
        cat = enc.fit_transform(df[cat_cols].fillna("<MISSING>").astype(str)).astype(np.float32)
        x = np.concatenate([num_norm, cat], axis=1)
        cat_meta = {"columns": cat_cols, "categories": [list(map(str, x)) for x in enc.categories_]}
    else:
        x = num_norm
        cat_meta = {"columns": [], "categories": []}

    if x.shape[1] > 128:
        # Deterministic variance-ranked selection; no data-dependent random projection.
        variances = x.var(axis=0)
        keep = np.argsort(-variances, kind="stable")[:128]
        x = x[:, keep]
        kept = keep.tolist()
    else:
        kept = list(range(x.shape[1]))
    logical_dim = x.shape[1]
    if logical_dim < 128:
        x = np.pad(x, ((0,0),(0,128-logical_dim)))

    # Fixed split order prevents buyer from choosing validation after seeing seller content.
    idx = np.arange(len(x))
    base_idx, remainder = train_test_split(idx, test_size=min(len(idx)-1, args.seller_rows + args.validation_rows), random_state=args.seed, stratify=y)
    val_idx, seller_idx = train_test_split(remainder, test_size=args.seller_rows, random_state=args.seed+1, stratify=y[remainder])
    val_idx = val_idx[:args.validation_rows]
    seller_idx = seller_idx[:args.seller_rows]

    for name, split in (("base", base_idx), ("validation", val_idx), ("seller", seller_idx)):
        np.savez_compressed(args.output / f"{name}.npz", x=x[split], y=y[split], original_index=split)

    policy = {
        "version": 1,
        "seed": args.seed,
        "label_mapping": {str(labels[0]): -1, str(labels[1]): 1},
        "numeric_columns": num_cols,
        "numeric_median": medians.to_dict(),
        "numeric_lower": q01.to_dict(),
        "numeric_scale": scale.to_dict(),
        "categorical": cat_meta,
        "kept_feature_indices": kept,
        "logical_feature_count": logical_dim,
        "physical_feature_count": 128,
        "fixed_point": "Q16.16",
    }
    (args.output / "preprocessing-policy.json").write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

    # Canonicalizer CSV contains already-quantized int32 values.
    for name in ("validation", "seller"):
        z = np.load(args.output / f"{name}.npz")
        q = round_even_q16(z["x"])
        timestamp = np.full((len(q),1), 1_700_000_000, dtype=np.int64)
        frame = pd.DataFrame(np.concatenate([z["y"][:,None], timestamp, q], axis=1))
        frame.to_csv(args.output / f"{name}-canonical-input.csv", index=False, header=False)

if __name__ == "__main__":
    main()
