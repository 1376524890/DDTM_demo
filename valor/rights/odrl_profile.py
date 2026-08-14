"""W3C ODRL 语义映射（规范 §3.2、§12）。

权利表达采用 ODRL-compatible profile：Permission、Prohibition、Duty、Constraint
可映射到 RightsBundle 字段；但原型内部保持类型化结构，不解析任意 RDF 图。

本模块仅做 ODRL 概念 → RightsBundle 的说明性映射（供审计/文档/导出），
不承担核心计算中的任意 RDF 解析。
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import RightsBundle


@dataclass(frozen=True)
class ODRLProfile:
    """ODRL 语义映射说明。

    用于把 RightsBundle 导出为 ODRL 风格的规则描述（Permission/Prohibition/
    Duty/Constraint），保持与 W3C ODRL Information Model 兼容。
    """

    permission_action: str = "reproduce"
    prohibition_action: str | None = None
    duty_action: str | None = None
    constraints: tuple[dict, ...] = ()

    @classmethod
    def from_bundle(cls, rb: RightsBundle) -> "ODRLProfile":
        """从 RightsBundle 生成 ODRL 语义映射。"""
        constraints: list[dict] = [
            {"constraint": "count", "operator": "lte", "operand": rb.q},
            {"constraint": "datetime", "operator": "gte", "operand": rb.t0},
            {"constraint": "datetime", "operator": "lte", "operand": rb.t1},
            {"constraint": "purpose", "operator": "eq",
             "operand": sorted(rb.purposes)},
        ]
        # 排他性 → prohibition：禁止第三方同权利
        prohibitions = ("reproduce" if rb.exclusivity else None)
        # 删除义务 → duty
        duty = ("delete" if rb.delete_duty else None)
        return cls(
            permission_action="reproduce",
            prohibition_action=prohibitions,
            duty_action=duty,
            constraints=tuple(constraints),
        )

    def to_plain(self) -> dict:
        return {
            "permission": self.permission_action,
            "prohibition": self.prohibition_action,
            "duty": self.duty_action,
            "constraints": list(self.constraints),
        }
