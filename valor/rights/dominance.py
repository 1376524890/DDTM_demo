"""权利支配与组合套利约束（规范 §32）。

若 R1 ⪰ R2（R1 包含 R2 的所有许可），同一 buyer、同一价格快照下应满足
    P(R1) >= P(R2)。
若 R 可由一组较小权利组合获得，则无组合套利要求：
    P(R) <= Σ_i P(R_i)。
该约束作用于 rights menu generation，不强行把不同 buyer 的价格排序到同一全局菜单。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import RightsBundle


@dataclass(frozen=True)
class DominanceChecker:
    """权利支配关系检查器（Phase 0 提供支配判断接口）。

    完整的价格约束（P(R1)>=P(R2)、P(R)<=ΣP(Ri)）在 Phase 5 pricing 中
    接入 rights menu；本模块定义支配关系判定，供菜单生成复用。
    """

    def dominates(self, a: RightsBundle, b: RightsBundle) -> bool:
        """判断 a 是否支配 b（a ⪰ b）：a 包含 b 的全部许可。

        判定维度（原型最小集）：排他、转授权、衍生、用途范围、使用次数、有效期。
        """
        # 排他权更强（a 排他或 b 不排他时 a 更"强"）
        if a.exclusivity and not b.exclusivity:
            pass
        elif b.exclusivity and not a.exclusivity:
            return False
        # 转授权/衍生：a 至少与 b 相当
        if not a.redistribution and b.redistribution:
            return False
        if not a.derivative and b.derivative:
            return False
        # 用途集合：a 覆盖 b
        if not b.purposes.issubset(a.purposes):
            return False
        # 使用次数：a 配额 >= b
        if a.q < b.q:
            return False
        # 有效期：a 覆盖 b 的 [t0,t1]
        if a.t0 > b.t0 or a.t1 < b.t1:
            return False
        return True

    def check_dominance_price(
        self, price: dict[str, float], a: RightsBundle, b: RightsBundle
    ) -> list[str]:
        """校验支配价格约束 P(R_a) >= P(R_b)；返回违反信息列表。

        price: {rights_hash: price}。
        """
        violations: list[str] = []
        if self.dominates(a, b):
            if price.get(a.rights_hash, 0.0) < price.get(b.rights_hash, 0.0):
                violations.append(
                    f"支配约束违反: P({a.r_class}) < P({b.r_class}) 但 R_a ⪰ R_b"
                )
        return violations

    def check_no_arbitrage(
        self, price: dict[str, float], bundle: RightsBundle, parts: list[RightsBundle]
    ) -> list[str]:
        """校验组合套利约束 P(R_bundle) <= Σ_i P(R_i)。"""
        violations: list[str] = []
        bundle_price = price.get(bundle.rights_hash, 0.0)
        parts_sum = sum(price.get(p.rights_hash, 0.0) for p in parts)
        if bundle_price > parts_sum:
            violations.append(
                f"组合套利约束违反: P(bundle)={bundle_price} > Σ P(parts)={parts_sum}"
            )
        return violations
