"""候选卖方批次（规范 §56 CandidateSellerBatch）。

RQ1 交易单位为 D_k = CandidateSellerBatch_k，不把每一行默认视作一笔交易。
K 与每批次行数由 experiment config 显式提供（ResolvedParameter）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CandidateBatch:
    """一个候选卖方批次 D_k。"""

    batch_id: int
    row_idx: np.ndarray
    X: pd.DataFrame
    y: pd.Series

    def size(self) -> int:
        return len(self.X)


def make_candidate_batches(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    seller_pool_idx: np.ndarray,
    n_batches: int,
    rows_per_batch: int,
    seed: int,
) -> list[CandidateBatch]:
    """从 SellerPool 生成 K 个互斥候选卖方批次（§56）。

    Args:
        X/y: 全量特征/标签
        seller_pool_idx: 卖方池行索引
        n_batches: 候选批次数量 K
        rows_per_batch: 每批行数
        seed: 随机种子（保证可复现）
    """
    if n_batches < 1:
        raise ValueError("n_batches 必须 >= 1")
    if rows_per_batch < 1:
        raise ValueError("rows_per_batch 必须 >= 1")

    pool = np.sort(np.asarray(seller_pool_idx, dtype=int))
    rng = np.random.default_rng(seed)
    rng.shuffle(pool)

    total_needed = n_batches * rows_per_batch
    if total_needed > len(pool):
        raise ValueError(
            f"卖方池样本不足: 需要 {total_needed} 行（{n_batches}×{rows_per_batch}），"
            f"卖方池仅 {len(pool)} 行"
        )

    batches: list[CandidateBatch] = []
    for k in range(n_batches):
        idx = pool[k * rows_per_batch:(k + 1) * rows_per_batch]
        batches.append(
            CandidateBatch(
                batch_id=k,
                row_idx=idx,
                X=X.iloc[idx].reset_index(drop=True),
                y=y.iloc[idx].reset_index(drop=True),
            )
        )
    return batches
