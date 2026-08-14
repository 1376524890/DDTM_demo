"""数据管线（规范 §55 四角色划分、§56 候选卖方批次、§15.4 注入）。

- download:         真实公开 tabular 二分类数据集加载（离线安全，sklearn 内置）
- preprocess:       基础预处理（数值化、缺失处理、归一化）
- split_roles:      四角色划分 BaseTrain/SellerPool/ValuationValidation/FinalEvaluation（§55）
- transaction_batches: 候选卖方批次 CandidateSellerBatch（§56）
- ground_truth:     受控 ground truth 标签
- injection:        质量错误受控注入（§15.4 InjectionSpec）
"""

from .download import load_dataset
from .split_roles import split_roles_four_way, FourWaySplit
from .transaction_batches import make_candidate_batches
from .ground_truth import GroundTruth
from .injection import (
    InjectionSpec,
    Injector,
    inject_errors,
    InjectionKind,
)

__all__ = [
    "load_dataset",
    "split_roles_four_way",
    "FourWaySplit",
    "make_candidate_batches",
    "GroundTruth",
    "InjectionSpec",
    "Injector",
    "inject_errors",
    "InjectionKind",
]
