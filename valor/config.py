"""配置加载与校验：类型化 dataclass + JSON，参数显式配置、缺失即报错。

设计原则（Phase 0 gate + D12）：
- 所有论文参数必须在 JSON 配置中显式给出，**缺失直接抛错**，禁止"无来源默认值"。
- 经济参数必须声明统一货币单位 [CU]（D12），config validation 检查单位一致性。
- 提供 load_config() 从 JSON 加载并构造类型化对象。
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigError(ValueError):
    """配置缺失/非法/单位不一致时抛出。"""

    pass


# 统一货币单位标识（D12）
CURRENCY_UNIT = "CU"


def _require(cond: bool, msg: str) -> None:
    """显式校验，不满足即抛 ConfigError。"""
    if not cond:
        raise ConfigError(msg)


def _require_field(d: Dict[str, Any], key: str, ctx: str) -> Any:
    """要求 JSON dict 中某字段必须显式存在（缺则报错）。"""
    if key not in d:
        raise ConfigError(f"[{ctx}] 缺失必需参数: {key}（禁止无来源默认值）")
    return d[key]


@dataclasses.dataclass
class DataConfig:
    """数据配置（D5/D6/D17）。"""

    dataset_name: str
    manifest_path: str
    n_candidates: int  # candidate seller batch 数量 K（D5）
    n_candidate_rows: int  # 每个 candidate batch 的行数
    split_seed: int  # 四角色划分种子（D17）

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DataConfig":
        _require_field(d, "dataset_name", "data")
        _require_field(d, "manifest_path", "data")
        n_cand = _require_field(d, "n_candidates", "data")
        n_rows = _require_field(d, "n_candidate_rows", "data")
        seed = _require_field(d, "split_seed", "data")
        _require(n_cand >= 1, "n_candidates 必须 >= 1")
        _require(n_rows >= 1, "n_candidate_rows 必须 >= 1")
        return cls(
            dataset_name=d["dataset_name"],
            manifest_path=d["manifest_path"],
            n_candidates=n_cand,
            n_candidate_rows=n_rows,
            split_seed=seed,
        )


@dataclasses.dataclass
class PayoffMatrix:
    """cost-sensitive payoff 矩阵（D7），行=true label，列=predicted。

    R_b = [[r_TN, r_FP],
           [r_FN, r_TP]]
    单位 [CU]。此矩阵是经济映射 g_b 的核心输入。
    """

    r_tn: float
    r_fp: float
    r_fn: float
    r_tp: float
    currency: str = CURRENCY_UNIT

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PayoffMatrix":
        _require_field(d, "r_tn", "economics.payoff")
        _require_field(d, "r_fp", "economics.payoff")
        _require_field(d, "r_fn", "economics.payoff")
        _require_field(d, "r_tp", "economics.payoff")
        # 单位校验（D12）：payoff 必须声明为 [CU]
        _require(d.get("currency", CURRENCY_UNIT) == CURRENCY_UNIT,
                 f"payoff 货币单位必须为 {CURRENCY_UNIT}")
        return cls(
            r_tn=d["r_tn"],
            r_fp=d["r_fp"],
            r_fn=d["r_fn"],
            r_tp=d["r_tp"],
            currency=d.get("currency", CURRENCY_UNIT),
        )

    def to_plain(self) -> Dict[str, Any]:
        """返回 JSON 原生 dict（2x2 矩阵形式，便于阅读）。"""
        return {
            "matrix": [
                [self.r_tn, self.r_fp],  # y=0: TN, FP
                [self.r_fn, self.r_tp],  # y=1: FN, TP
            ],
            "currency": self.currency,
        }


@dataclasses.dataclass
class AuditLossMatrix:
    """审计阶段决策损失矩阵 ℓ(d_Q, x)（机制文档 §5.3）。

    d_Q ∈ {ACCEPT, REJECT, TERMINATE}，x ∈ {G, L, B}。
    单位 [CU]（D12），与审计支付、MV_A 同单位。
    索引: loss[decision][state]
    """

    loss: Dict[str, Dict[str, float]]
    currency: str = CURRENCY_UNIT

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuditLossMatrix":
        _require_field(d, "loss", "economics.audit_loss_matrix")
        _require(d.get("currency", CURRENCY_UNIT) == CURRENCY_UNIT,
                 f"audit_loss_matrix 货币单位必须为 {CURRENCY_UNIT}")
        loss = d["loss"]
        # 必须覆盖全部决策 × 状态
        for dec in ("ACCEPT", "REJECT", "TERMINATE"):
            _require(dec in loss, f"audit_loss_matrix 缺决策 {dec}")
            for st in ("G", "L", "B"):
                _require(st in loss[dec], f"audit_loss_matrix[{dec}] 缺状态 {st}")
        return cls(loss=loss, currency=d.get("currency", CURRENCY_UNIT))

    def get(self, decision: str, state: str) -> float:
        """读取 ℓ(decision, state)。"""
        return self.loss[decision][state]

    def to_plain(self) -> Dict[str, Any]:
        return {"loss": self.loss, "currency": self.currency}


@dataclasses.dataclass
class EconomicsConfig:
    """经济参数集合（D12 统一 [CU]）。"""

    payoff: PayoffMatrix
    audit_loss_matrix: AuditLossMatrix
    currency: str = CURRENCY_UNIT


@dataclasses.dataclass
class LabConfig:
    """顶层实验配置，聚合各子配置。"""

    data: DataConfig
    economics: EconomicsConfig
    # reproducibility 元数据
    experiment_id: str
    seed: int

    @classmethod
    def load(cls, config_path: str) -> "LabConfig":
        """从 JSON 加载完整配置。

        任何必需参数缺失都会抛 ConfigError（Phase 0 gate）。
        """
        path = Path(config_path)
        if not path.exists():
            raise ConfigError(f"配置文件不存在: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))

        _require_field(raw, "experiment_id", "root")
        _require_field(raw, "seed", "root")
        _require_field(raw, "data", "root")
        _require_field(raw, "economics", "root")

        return cls(
            experiment_id=raw["experiment_id"],
            seed=raw["seed"],
            data=DataConfig.from_dict(raw["data"]),
            economics=EconomicsConfig(
                payoff=PayoffMatrix.from_dict(
                    _require_field(raw["economics"], "payoff", "economics")
                ),
                audit_loss_matrix=AuditLossMatrix.from_dict(
                    _require_field(
                        raw["economics"], "audit_loss_matrix", "economics"
                    )
                ),
            ),
        )
