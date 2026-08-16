"""Privacy Audit 受控 corruption 校准（PPA-7）。

对齐方案 §27：检测能力不能用理论公式直接当 likelihood，必须通过 calibration 实验产生。

对每种 breach 类型（label corruption / pixel corruption / 正常 G）和多组 k，
跑多次 COMMIT_CHALLENGE 审计，统计：
    P(PASS | G, action)
    P(CLAIM_NOT_SUPPORTED | G, action)
    P(BREACH_EVIDENCE | B, action)   # 由 Merkle 篡改注入
    ...

产出 ActionLikelihoodArtifact（供 Audit-VOI 的 Λ_j 使用）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from valor.core.hashing import content_hash

from .challenge import generate_challenge
from .claims import AggregateClaim, make_claim
from .commitment import CommittedDatasetStore
from .models import ClaimType, PrimitiveResult
from .opening import verify_opening
from .primitives import run_primitive
from .verifier import CommitChallengeVerifier


@dataclass
class LikelihoodCell:
    """一个 (breach_type, k) 的检测统计。"""

    breach_type: str  # GOOD | LABEL_CORRUPT | MERKLE_TAMPER
    k: int
    n_runs: int
    pass_rate: float
    claim_not_supported_rate: float
    breach_rate: float

    def to_plain(self) -> dict:
        return {
            "breach_type": self.breach_type, "k": self.k, "n_runs": self.n_runs,
            "pass_rate": self.pass_rate,
            "claim_not_supported_rate": self.claim_not_supported_rate,
            "breach_rate": self.breach_rate,
        }


def _corrupt_labels(y: np.ndarray, frac: float, rng) -> np.ndarray:
    y = y.copy()
    n = len(y)
    idx = rng.choice(n, size=int(frac * n), replace=False)
    for i in idx:
        y[i] = rng.choice([c for c in range(10) if c != int(y[i])])
    return y


def calibrate_likelihood(
    *,
    X: np.ndarray, y: np.ndarray,
    challenge_sizes: list[int],
    n_runs: int = 3,
    label_corruption_frac: float = 0.2,
    seed: int = 0,
) -> dict:
    """对每种 breach 类型 + 每组 k 跑 commit-challenge，统计检测率。

    返回 {"cells": [...], "likelihood_artifact": {...}}。
    """
    rng = np.random.default_rng(seed)
    cells: list[LikelihoodCell] = []

    for k in challenge_sizes:
        # ---- GOOD：干净 label ----
        pass_cnt = claim_cnt = breach_cnt = 0
        for run in range(n_runs):
            out = _single_run(X, y, k, rng, corrupt=False, tamper=False,
                              seed=seed + run)
            if out == "PASS":
                pass_cnt += 1
            elif out == "CLAIM_NOT_SUPPORTED":
                claim_cnt += 1
            elif out == "BREACH_EVIDENCE":
                breach_cnt += 1
        cells.append(LikelihoodCell(
            "GOOD", k, n_runs, pass_cnt / n_runs,
            claim_cnt / n_runs, breach_cnt / n_runs))

        # ---- LABEL_CORRUPT ----
        pass_cnt = claim_cnt = breach_cnt = 0
        for run in range(n_runs):
            out = _single_run(X, y, k, rng, corrupt=True, tamper=False,
                              seed=seed + run + 100,
                              corrupt_frac=label_corruption_frac)
            if out == "PASS":
                pass_cnt += 1
            elif out == "CLAIM_NOT_SUPPORTED":
                claim_cnt += 1
            elif out == "BREACH_EVIDENCE":
                breach_cnt += 1
        cells.append(LikelihoodCell(
            "LABEL_CORRUPT", k, n_runs, pass_cnt / n_runs,
            claim_cnt / n_runs, breach_cnt / n_runs))

        # ---- MERKLE_TAMPER：seller 篡改行 → BREACH ----
        pass_cnt = claim_cnt = breach_cnt = 0
        for run in range(n_runs):
            out = _single_run(X, y, k, rng, corrupt=False, tamper=True,
                              seed=seed + run + 200)
            if out == "PASS":
                pass_cnt += 1
            elif out == "CLAIM_NOT_SUPPORTED":
                claim_cnt += 1
            elif out == "BREACH_EVIDENCE":
                breach_cnt += 1
        cells.append(LikelihoodCell(
            "MERKLE_TAMPER", k, n_runs, pass_cnt / n_runs,
            claim_cnt / n_runs, breach_cnt / n_runs))

    likelihood_artifact = {
        "kind": "privacy_audit_likelihood",
        "cells": [c.to_plain() for c in cells],
        "label_corruption_frac": label_corruption_frac,
        "n_runs": n_runs,
        "artifact_hash": content_hash({
            "cells": [c.to_plain() for c in cells],
            "label_corruption_frac": label_corruption_frac,
            "n_runs": n_runs,
        }),
    }
    return {"cells": cells, "likelihood_artifact": likelihood_artifact}


def _single_run(X, y, k, rng, *, corrupt, tamper, seed, corrupt_frac=0.2) -> str:
    """单次 commit-challenge 运行，返回 PrimitiveResult。"""
    from valor.seller import SellerCommittedDataset

    store = CommittedDatasetStore("/tmp/pa-calib")
    y_use = _corrupt_labels(y, corrupt_frac, rng) if corrupt else y
    seller = SellerCommittedDataset.create(
        store, dataset_id=f"calib-{seed}", version="v1",
        X=X, y=y_use, schema_hash="s" * 64)
    claim = make_claim(
        claim_type=ClaimType.LABEL_DISTRIBUTION,
        value={str(c): float(np.sum(y == c)) for c in range(10)},
        dataset_commitment_hash=seller.commitment.commitment_hash)
    ch = generate_challenge(task_hash=f"t-{seed}", action_id="a1",
                            n_rows=len(X), k=k, nonce=rng.bytes(32))
    opens = seller.open_rows(list(ch.indices))

    # 若 tamper：篡改第一个 opening 的 row_payload
    if tamper and opens:
        from .canonicalize import canonical_row_from_payload, canonical_mnist_row
        from .opening import make_opening
        o = opens[0]
        idx, img, label = canonical_row_from_payload(o.row_payload, index=o.index)
        img = img.copy()
        img[0] = (int(img[0]) + 1) % 256
        opens[0] = make_opening(
            index=o.index, row_payload=canonical_mnist_row(o.index, img, label),
            salt=bytes.fromhex(o.salt), proof=o.proof)

    from .verifier import AuditExecutionContext

    verifier = CommitChallengeVerifier("node-0")
    ctx = AuditExecutionContext(
        commitment=seller.commitment, claim=claim, challenge=ch, openings=opens)
    ev = verifier.execute(task_hash=f"t-{seed}", primitive_id="LabelDistributionAudit",
                          ctx=ctx)
    return ev.result


# ---------------------------------------------------------------------------
# V2：真实三状态经验似然（删除人工 L=0.5，Dirichlet smoothing）
# ---------------------------------------------------------------------------
def calibrate_empirical_likelihood_v2(
    *,
    X: np.ndarray, y: np.ndarray,
    challenge_sizes: list[int],
    n_runs: int = 4,
    label_latent_frac: float = 0.05,  # L：轻度污染（诚实但不适合）
    label_breach_frac: float = 0.3,   # B：严重污染/篡改（真实 breach）
    seed: int = 0,
    alpha: dict[str, float] | None = None,
) -> dict:
    """构造真实 G/L/B 三状态经验似然，冻结 artifact。

    三种 ground truth（论文强调 L≠B）：
        G : 数据和声明都正常
        L : 轻度 label 污染（卖方诚实但 buyer-specific suitability 不足）
        B : Merkle 篡改（commitment 与揭示数据不一致，真实 seller breach）

    对每个 (state, k)，跑 n_runs 次 COMMIT_CHALLENGE，收集 (state, outcome)
    计数，用 Dirichlet smoothing 估计 Λ(y|x)。R_cal 只用校准数据。
    """
    from valor.engine.calibration_v2 import (
        DEFAULT_ALPHA,
        OUTCOMES,
        EmpiricalLikelihood,
        freeze_empirical_likelihood,
    )

    rng = np.random.default_rng(seed)
    # 每个 k 一个独立似然（challenge_size 影响检测能力）
    likelihoods = {}
    for k in challenge_sizes:
        lik = EmpiricalLikelihood(
            action_id=f"a-{k}", breach_family="structural",
            alpha=alpha or dict(DEFAULT_ALPHA))
        for run in range(n_runs):
            # G：干净
            g_out = _single_run(X, y, k, rng, corrupt=False, tamper=False,
                                seed=seed + run)
            lik.add("G", g_out)
            # L：轻度 label 污染（诚实但不适合）
            l_out = _single_run(X, y, k, rng, corrupt=True, tamper=False,
                                seed=seed + run + 100,
                                corrupt_frac=label_latent_frac)
            lik.add("L", l_out)
            # B：Merkle 篡改（真实 breach）→ 必然 BREACH_EVIDENCE
            b_out = _single_run(X, y, k, rng, corrupt=False, tamper=True,
                                seed=seed + run + 200)
            lik.add("B", b_out)
        likelihoods[str(k)] = lik

    # 冻结 artifact（每个 k 一个 rows；审计时按 k 取）
    from valor.core.hashing import content_hash

    cal_hash = content_hash({"X": X.tobytes(), "y": y.tobytes(), "seed": seed})
    frozen = {
        "kind": "audit_likelihood_v2",
        "challenge_sizes": challenge_sizes,
        "n_runs": n_runs,
        "label_latent_frac": label_latent_frac,
        "label_breach_frac": label_breach_frac,
        "likelihoods": {
            k: freeze_empirical_likelihood(
                lik, policy_hash="p" * 64, calibration_hash=cal_hash)
            for k, lik in likelihoods.items()
        },
    }
    frozen["artifact_hash"] = content_hash({
        "kind": frozen["kind"],
        "likelihoods": frozen["likelihoods"],
        "n_runs": n_runs, "seed": seed,
    })
    return frozen


__all__ = ["LikelihoodCell", "calibrate_likelihood", "calibrate_empirical_likelihood_v2"]
