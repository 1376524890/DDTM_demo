"""四角色数据划分（规范 §55）。

BaseTrain ∩ SellerPool ∩ ValuationValidation ∩ FinalEvaluation = ∅

- BaseTrain：买方已有训练信息
- SellerPool：候选卖方批次来源
- ValuationValidation：估值器允许使用的 reference/eval 数据
- FinalEvaluation：仅用于 Oracle realised utility 与最终实验评价

所有角色划分比例来自显式参数（ResolvedParameter），禁止隐式默认。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class FourWaySplit:
    """四角色行索引（互不相交，§55）。"""

    base_train_idx: np.ndarray
    seller_pool_idx: np.ndarray
    valuation_validation_idx: np.ndarray
    final_evaluation_idx: np.ndarray

    def __post_init__(self) -> None:
        self.assert_disjoint()

    def assert_disjoint(self) -> None:
        """断言四角色互不相交（§55）。"""
        sets = [
            ("base_train", set(map(int, self.base_train_idx))),
            ("seller_pool", set(map(int, self.seller_pool_idx))),
            ("valuation_validation", set(map(int, self.valuation_validation_idx))),
            ("final_evaluation", set(map(int, self.final_evaluation_idx))),
        ]
        for i in range(len(sets)):
            for j in range(i + 1, len(sets)):
                inter = sets[i][1] & sets[j][1]
                if inter:
                    raise ValueError(
                        f"角色 {sets[i][0]} 与 {sets[j][0]} 重叠 {len(inter)} 行（§55 违反）"
                    )

    def frame(self, df: pd.DataFrame, idx: np.ndarray) -> pd.DataFrame:
        return df.iloc[np.sort(idx)].reset_index(drop=True)


def split_roles_four_way(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    seed: int,
    base_train_frac: float,
    seller_pool_frac: float,
    valuation_validation_frac: float,
) -> FourWaySplit:
    """四角色划分。

    剩余比例自动归入 FinalEvaluation（保证覆盖全样本且互斥）。
    """
    n = len(X)
    if not (0 <= base_train_frac <= 1 and 0 <= seller_pool_frac <= 1
            and 0 <= valuation_validation_frac <= 1):
        raise ValueError("各角色比例必须在 [0,1]")
    if base_train_frac + seller_pool_frac + valuation_validation_frac >= 1.0:
        raise ValueError("前三角色比例之和必须 < 1（为 FinalEvaluation 留样本）")

    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)

    def take(frac: float, start: int) -> tuple[np.ndarray, int]:
        m = int(round(frac * n))
        part = idx[start:start + m]
        return part, start + m

    base, p = take(base_train_frac, 0)
    seller, p = take(seller_pool_frac, p)
    val, p = take(valuation_validation_frac, p)
    final = idx[p:]

    return FourWaySplit(
        base_train_idx=base,
        seller_pool_idx=seller,
        valuation_validation_idx=val,
        final_evaluation_idx=final,
    )
