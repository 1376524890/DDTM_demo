"""ResolvedParameter 与参数清单模型（规范 §5 / §54.1）。

任何进入论文公式和交易决策的参数都必须表示为一个 ResolvedParameter，
携带来源类型、证据引用、单位、版本哈希；禁止给 value 设置业务默认值。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.enums import ParamSource
from valor.core.errors import UnresolvedParameterError
from valor.core.hashing import content_hash


@dataclass(frozen=True)
class ResolvedParameter:
    """已解析参数（规范 §54.1）。

    注意：value 字段没有默认值 —— 任何业务参数都必须在构造时显式给出，
    否则直接报错，杜绝"无来源默认值"（规范 §5.3）。
    """

    name: str
    value: Any
    unit: str
    source_kind: ParamSource
    source_ref: str
    version_hash: str
    # 可选：不确定度/区间（规范 §5.1）
    uncertainty: float | None = None
    resolved_at: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise UnresolvedParameterError("参数名不能为空")
        if not self.source_ref:
            raise UnresolvedParameterError(
                f"[{self.name}] 缺少证据引用 source_ref（MISSING_EVIDENCE_REF）"
            )
        if not self.version_hash:
            raise UnresolvedParameterError(
                f"[{self.name}] 缺少版本哈希 version_hash"
            )

    def to_plain(self) -> dict:
        """返回 JSON 原生表示。"""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source_kind": self.source_kind.value,
            "source_ref": self.source_ref,
            "version_hash": self.version_hash,
            "uncertainty": self.uncertainty,
            "resolved_at": self.resolved_at,
        }


@dataclass(frozen=True)
class ParameterManifest:
    """一组参数的清单（含整体哈希，用于可复现性）。"""

    parameters: tuple[ResolvedParameter, ...] = field(default_factory=tuple)

    def by_name(self) -> dict[str, ResolvedParameter]:
        return {p.name: p for p in self.parameters}

    def require(self, name: str) -> ResolvedParameter:
        """按名取参数；缺失抛 UNRESOLVED_PARAMETER。"""
        p = self.by_name().get(name)
        if p is None:
            raise UnresolvedParameterError(
                f"[{name}] 参数未解析（UNRESOLVED_PARAMETER）"
            )
        return p

    @property
    def manifest_hash(self) -> str:
        """对全部参数做确定性内容哈希（规范 §68 parameters.manifest_hash）。"""
        return content_hash(tuple(p.to_plain() for p in self.parameters))

    def to_plain(self) -> dict:
        return {
            "manifest_hash": self.manifest_hash,
            "parameters": [p.to_plain() for p in self.parameters],
        }
