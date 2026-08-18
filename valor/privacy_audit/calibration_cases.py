"""Privacy Audit 受控 corruption 实验 case（PPA-7）。

本模块只负责**产生 observation**（一次 commit-challenge 的运行结果），
**不允许**自己 freeze 最终 calibration artifact。唯一 freeze 方是
`valor/engine/calibration_runner.py`（empirical likelihood 估计 + 证书冻结）。

三种 ground truth case（论文强调 L≠B 严格不同）：
    G : seller honest + data suitable
        committed dataset = D_G，claim = truthful(D_G)，无篡改。
    L : seller honest + claims truthful，但 buyer-specific suitability 不足
        committed dataset = D_L，claim = truthful(D_L)，commitment = truthful(D_L)，
        只是 D_L 对 buyer task 的效用/质量不足（轻度污染/类不平衡/域偏移）。
        只能导致 CLAIM_NOT_SUPPORTED / QUALITY_FAIL，绝不能是 BREACH_EVIDENCE。
    B : 真实 seller breach
        false claim / Merkle opening mismatch / post-commit 修改 / delivery
        substitution / metadata fraud → 必然 BREACH_EVIDENCE。
"""

from __future__ import annotations

import numpy as np

from valor.core.hashing import content_hash

from .challenge import generate_challenge
from .claims import make_claim
from .commitment import CommittedDatasetStore
from .models import ClaimType
from .opening import make_opening
from .verifier import CommitChallengeVerifier


def _corrupt_labels(y: np.ndarray, frac: float, rng) -> np.ndarray:
    """轻度 label 污染（L）：诚实但 buyer-specific 质量不足，非 breach。"""
    y = y.copy()
    n = len(y)
    idx = rng.choice(n, size=int(frac * n), replace=False)
    for i in idx:
        y[i] = rng.choice([c for c in range(10) if c != int(y[i])])
    return y


def _run_commit_challenge(
    X: np.ndarray, y: np.ndarray, k: int, seed: int, *, tamper: bool,
) -> str:
    """单次 commit-challenge 运行，返回 PrimitiveResult outcome。"""
    from valor.seller import SellerCommittedDataset

    store = CommittedDatasetStore("/tmp/pa-calib")
    seller = SellerCommittedDataset.create(
        store, dataset_id=f"calib-{seed}", version="v1",
        X=X, y=y, schema_hash=content_hash({"schema": "MNIST-784"}))
    claim = make_claim(
        claim_type=ClaimType.LABEL_DISTRIBUTION,
        value={str(c): float(np.sum(y == c)) for c in range(10)},
        dataset_commitment_hash=seller.commitment.commitment_hash)
    rng = np.random.default_rng(seed)
    ch = generate_challenge(task_hash=f"t-{seed}", action_id="a1",
                            n_rows=len(X), k=k, nonce=rng.bytes(32))
    opens = seller.open_rows(list(ch.indices))

    # 若 tamper：篡改第一个 opening 的 row_payload（真实 breach）
    if tamper and opens:
        from .canonicalize import canonical_mnist_row, canonical_row_from_payload

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
    ev = verifier.execute(task_binding_hash=f"t-{seed}",
                          primitive_id="LabelDistributionAudit", ctx=ctx)
    return ev.result


def run_good_case(X: np.ndarray, y: np.ndarray, k: int, *, seed: int) -> str:
    """G：seller honest + data suitable。干净数据，无篡改。"""
    return _run_commit_challenge(X, y, k, seed, tamper=False)


def run_latent_case(
    X: np.ndarray, y: np.ndarray, k: int, *,
    seed: int, latent_frac: float = 0.05,
) -> str:
    """L：seller honest + claims truthful，buyer-specific 质量不足。

    轻度 label 污染（诚实但不适合）；commitment 与 claim 一致，只触发
    CLAIM_NOT_SUPPORTED / QUALITY_FAIL，不触发 BREACH_EVIDENCE。
    """
    rng = np.random.default_rng(seed)
    y_use = _corrupt_labels(y, latent_frac, rng)
    return _run_commit_challenge(X, y_use, k, seed, tamper=False)


def run_breach_case(
    X: np.ndarray, y: np.ndarray, k: int, *, seed: int,
) -> str:
    """B：真实 seller breach。篡改 opening → Merkle mismatch → BREACH_EVIDENCE。"""
    return _run_commit_challenge(X, y, k, seed, tamper=True)


def collect_observations(
    X: np.ndarray, y: np.ndarray, *, challenge_sizes: list[int],
    n_runs: int, latent_frac: float = 0.05, seed: int = 0,
) -> dict[str, dict[str, str]]:
    """对每个 (challenge_size, state) 跑 n_runs 次，收集 (state -> [outcome])。

    只产出 observation，不 freeze 任何 artifact。返回
        {str(k): {"G": [outcome,...], "L": [...], "B": [...]}}
    """
    out: dict[str, dict[str, str]] = {}
    for k in challenge_sizes:
        states: dict[str, list[str]] = {"G": [], "L": [], "B": []}
        for run in range(n_runs):
            states["G"].append(run_good_case(X, y, k, seed=seed + run))
            states["L"].append(run_latent_case(X, y, k, seed=seed + run,
                                               latent_frac=latent_frac))
            states["B"].append(run_breach_case(X, y, k, seed=seed + run))
        out[str(k)] = {s: v for s, v in states.items()}
    return out


__all__ = [
    "run_good_case",
    "run_latent_case",
    "run_breach_case",
    "collect_observations",
]
