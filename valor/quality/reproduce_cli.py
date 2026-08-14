"""`python -m valor quality reproduce` 运行器（规范 §47 Q0 / §71）。

加载复现配置 → 构建目录 → 加载公开数据集 → 四角色划分 → 生成候选批次 →
注入 case → 对目录内全部 primitive 执行 Reference Reproduction Gate →
写出 reports/quality_reproduction/*.json。
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from valor.core.reproducibility import build_repro_metadata

from .catalog import default_catalog
from .reproduction import run_reproduction_gate

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_reproduce_config(config_path: str) -> dict:
    from valor.core.errors import ConfigError

    p = Path(config_path)
    if not p.exists():
        raise ConfigError(f"复现配置文件不存在: {p}")
    cfg = json.loads(p.read_text(encoding="utf-8"))
    if cfg.get("schema_version") != "1":
        from valor.core.errors import ConfigVersionUnsupportedError

        raise ConfigVersionUnsupportedError(f"不支持 schema 版本: {cfg.get('schema_version')}")
    return cfg


def _discretize(col, bins: int = 4, seed: int = 0) -> "pd.Series":
    """把数值列离散化为类别（供 categorical_shift 复现用，可复现）。"""
    import pandas as pd

    try:
        return pd.qcut(col.rank(method="first"), bins, labels=False).astype(str)
    except Exception:
        return (col > col.median()).astype(int).astype(str)


def run_quality_reproduce(config_path: str, *, out_dir: str = "reports/quality_reproduction") -> int:
    """执行质量复现并写报告。返回退出码。"""
    cfg = _load_reproduce_config(config_path)
    import pandas as pd

    from valor.data.download import load_dataset
    from valor.data.split_roles import split_roles_four_way
    from valor.data.injection import InjectionSpec, InjectionKind, inject_errors

    ds_cfg = cfg["dataset"]
    rep_cfg = cfg.get("reproduction", {})

    handle = load_dataset(ds_cfg["name"])
    X, y = handle.X, handle.y
    # 预处理（数值化/缺失），用 seller_pool 作为候选数据
    from valor.data.preprocess import preprocess
    X = preprocess(X, fill_strategy="none")

    split = split_roles_four_way(
        X, y, seed=ds_cfg["seed"],
        base_train_frac=ds_cfg["base_train_frac"],
        seller_pool_frac=ds_cfg["seller_pool_frac"],
        valuation_validation_frac=ds_cfg["valuation_validation_frac"],
    )
    # 候选批次（§56）：取第一个批次作为候选数据
    from valor.data.transaction_batches import make_candidate_batches
    batches = make_candidate_batches(
        X, y,
        seller_pool_idx=split.seller_pool_idx,
        n_batches=rep_cfg.get("n_batches", 3),
        rows_per_batch=rep_cfg.get("rows_per_batch", 50),
        seed=ds_cfg["seed"],
    )
    cand = batches[0]
    reference_df = X.iloc[split.valuation_validation_idx].reset_index(drop=True)

    # 注入 case（默认 label_flip，可覆盖）
    inj_cfg = (rep_cfg.get("injections") or [{"kind": "label_flip", "fraction": 0.2}])[0]
    spec = InjectionSpec(
        kind=InjectionKind(inj_cfg["kind"]),
        fraction=inj_cfg["fraction"],
        seed=inj_cfg.get("seed", ds_cfg["seed"]),
    )
    X_cand, y_cand, gt = inject_errors(cand.X, cand.y, spec)

    # 派生默认列（OBSERVED_DATA）并填充 params（config 显式值优先，缺失用默认补齐）
    first_num = list(X.select_dtypes(include=["number"]).columns)[0]
    default_params = {
        "ks_shift": {"column": first_num, "alpha_shift": 0.05, "floating_tolerance": 1e-6},
        "categorical_shift": {"column": first_num, "alpha_shift": 0.05, "floating_tolerance": 1e-3},
        "mmd": {"target_pvalue_resolution": 0.05, "n_permutations": 50, "floating_tolerance": 1e-4},
        "confident_learning": {"threshold_method": "mean", "floating_tolerance": 0.1, "min_gt_recall": 0.2},
        "metadata_claim_audit": {
            "claims": {"c1": {"predicate": "max_missing_rate", "column": first_num, "declared": 0.0}},
        },
    }
    given = dict(rep_cfg.get("params_by_algorithm", {}))
    pba: dict[str, dict] = {}
    for aid, defaults in default_params.items():
        merged = dict(defaults)
        merged.update(given.get(aid, {}))
        pba[aid] = merged

    # 对 categorical_shift 用离散化列（candidate 与 reference 各自离散化）
    cat_col = pba["categorical_shift"]["column"]
    cat_ref = _discretize(reference_df[cat_col], seed=ds_cfg["seed"])
    # 构造分类 case：替换列
    cand_cat = cand.X.copy()
    cand_cat[cat_col] = _discretize(cand_cat[cat_col], seed=ds_cfg["seed"])
    ref_cat = reference_df.copy()
    ref_cat[cat_col] = cat_ref

    # 运行 Gate B
    catalog = default_catalog()
    certificates = run_reproduction_gate(
        catalog,
        reference_df=reference_df,
        candidate_df=X_cand,
        y_candidate=y_cand,
        ground_truth=gt,
        params_by_algorithm=pba,
        created_at=datetime.now(timezone.utc).isoformat(),
        floating_tolerance=rep_cfg.get("floating_tolerance", 1e-5),
    )

    # 写报告
    out = REPO_ROOT / out_dir
    os.makedirs(out, exist_ok=True)
    summary = {
        "schema_version": "1",
        "dataset": handle.name,
        "gate_passed": {aid: c.passed for aid, c in certificates.items()},
        "distributed_enabled": catalog.distributed_ids(),
        "repro": build_repro_metadata(repo_root=str(REPO_ROOT)),
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for aid, cert in certificates.items():
        (out / f"{aid}.json").write_text(
            json.dumps(cert.to_plain(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 打印摘要
    print(f"数据集: {handle.name}")
    for aid, cert in certificates.items():
        print(f"  {aid:24s} Gate={'PASS' if cert.passed else 'FAIL'} "
              f"distributed={catalog.get(aid).distributed_enabled}")
    return 0 if all(c.passed for c in certificates.values()) else 1
