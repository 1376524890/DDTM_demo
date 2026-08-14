"""ResolvedParameter 与机制输出模型（检查单 B、规范 §5 / §54.1）。

- ResolvedParameter：外生/校准/市场发现/优化得到的**输入**参数，含 dtype、
  unit、source_kind、source_ref、resolved_at、version_hash、uncertainty/interval。
  value 无业务默认值；source_ref 有统一 URI schema；version_hash 校验为哈希。
- Interval：不确定度/区间的明确 schema（非自由字典）。
- MechanismResult / ComputedValue：公式与算法计算产生的**输出**，带 derived_from
  与 input_hashes，可向前追踪。与 ResolvedParameter 严格分离（检查单 B3）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.enums import ParamSource
from valor.core.errors import (
    MissingEvidenceRefError,
    UnresolvedParameterError,
)
from valor.core.hashing import content_hash, validate_hash

from .refs import validate_source_ref
from .units import validate_unit


def infer_dtype(value: Any) -> str:
    """从值推断 dtype 标签（bool 优先于 int，避免 bool 被当 int）。"""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    return type(value).__name__


@dataclass(frozen=True)
class Interval:
    """不确定度/区间 schema（检查单 B1：有明确 schema，非自由字典）。

    用于 uncertainty 或 certified range。
    """

    lower: float
    upper: float
    unit: str
    confidence: float | None = None  # 覆盖置信度（可选）

    def __post_init__(self) -> None:
        validate_unit(self.unit, name="Interval")
        if self.lower > self.upper:
            raise ValueError(f"Interval 下界大于上界: {self.lower} > {self.upper}")
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Interval 置信度越界: {self.confidence}")

    def to_plain(self) -> dict:
        return {
            "lower": self.lower,
            "upper": self.upper,
            "unit": self.unit,
            "confidence": self.confidence,
        }

    @classmethod
    def from_plain(cls, d: dict) -> "Interval":
        return cls(
            lower=d["lower"],
            upper=d["upper"],
            unit=d["unit"],
            confidence=d.get("confidence"),
        )


@dataclass(frozen=True)
class ResolvedParameter:
    """已解析参数（规范 §54.1 / 检查单 B1）。

    value 无业务默认值；dtype 可缺省（由 value 推断）。创建后不可变。
    """

    name: str
    value: Any
    unit: str
    source_kind: ParamSource
    source_ref: str
    version_hash: str
    dtype: str | None = None
    uncertainty: Interval | float | None = None
    resolved_at: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise UnresolvedParameterError("参数名不能为空")
        # dtype 缺省时由 value 推断（元数据，非业务默认值）
        if self.dtype is None:
            object.__setattr__(self, "dtype", infer_dtype(self.value))
        validate_unit(self.unit, name=self.name)
        # 来源类型必须是合法枚举
        if not isinstance(self.source_kind, ParamSource):
            raise UnresolvedParameterError(
                f"[{self.name}] source_kind 非法: {self.source_kind!r}"
            )
        # source_ref：缺失 → MISSING_EVIDENCE_REF；格式/scheme 非法 → INVALID_SOURCE_REF
        validate_source_ref(self.source_ref, self.source_kind)
        # version_hash：必须是合法哈希（小写 hex）
        validate_hash(self.version_hash, name=f"{self.name}.version_hash")
        # resolved_at：若提供必须是 UTC ISO（'Z' 或 +00:00）
        if self.resolved_at is not None and not (
            self.resolved_at.endswith("Z") or "+00:00" in self.resolved_at
        ):
            raise UnresolvedParameterError(
                f"[{self.name}] resolved_at 必须为 UTC ISO-8601: {self.resolved_at!r}"
            )

    def to_plain(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "dtype": self.dtype,
            "unit": self.unit,
            "source_kind": self.source_kind.value,
            "source_ref": self.source_ref,
            "version_hash": self.version_hash,
            "uncertainty": (
                self.uncertainty.to_plain()
                if isinstance(self.uncertainty, Interval)
                else self.uncertainty
            ),
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ResolvedParameter":
        """从字典构造（用于配置加载）。"""
        return cls(
            name=d["name"],
            value=d["value"],
            unit=d["unit"],
            source_kind=ParamSource(d["source_kind"]),
            source_ref=d["source_ref"],
            version_hash=d["version_hash"],
            dtype=d.get("dtype"),
            uncertainty=d.get("uncertainty"),
            resolved_at=d.get("resolved_at"),
        )


@dataclass(frozen=True)
class ComputedValue:
    """机制计算输出（检查单 B3）。

    与 ResolvedParameter 分离：表示由公式/算法计算产生的输出（如
    p_i^A、B_S^*、P_τ^*），而非外部可配置输入。
    """

    name: str
    value: Any
    unit: str
    formula_ref: str  # 产生该值的公式/函数引用
    derived_from: tuple[str, ...]  # 输入参数名
    input_hashes: tuple[str, ...]  # 输入参数内容哈希（向前追踪）

    def __post_init__(self) -> None:
        validate_unit(self.unit, name=self.name)

    def to_plain(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "formula_ref": self.formula_ref,
            "derived_from": list(self.derived_from),
            "input_hashes": list(self.input_hashes),
        }


# 语义别名（检查单 B3 推荐的第一种命名）
MechanismResult = ComputedValue


@dataclass(frozen=True)
class ParameterManifest:
    """一组输入参数的清单（含整体哈希，用于可复现性）。"""

    parameters: tuple[ResolvedParameter, ...] = field(default_factory=tuple)

    def by_name(self) -> dict[str, ResolvedParameter]:
        return {p.name: p for p in self.parameters}

    def require(self, name: str) -> ResolvedParameter:
        p = self.by_name().get(name)
        if p is None:
            raise UnresolvedParameterError(
                f"[{name}] 参数未解析（UNRESOLVED_PARAMETER）"
            )
        return p

    @property
    def manifest_hash(self) -> str:
        return content_hash(tuple(p.to_plain() for p in self.parameters))

    def to_plain(self) -> dict:
        return {
            "manifest_hash": self.manifest_hash,
            "parameters": [p.to_plain() for p in self.parameters],
        }
