"""权利束 / ODRL / 注册表 / 兼容 / 支配 / 机会成本（规范 §3.2、§32、§54.4）。

- models:             RightsBundle / RightsState（§3.2、§43、§54.4）
- odrl_profile:       W3C ODRL 语义映射（Permission/Prohibition/Duty/Constraint）
- registry:           活跃许可集合 L_D(t) 与注册（§32）
- compatibility:      Compatible(R_τ, L_D(t)) 重复出售约束（§32）
- dominance:          权利支配 / 组合套利约束（§32）
- opportunity_cost:   OC_S(R_τ) 卖方未来许可机会成本（§29）
"""

from .models import RightsBundle, RightsStateRecord
from .odrl_profile import ODRLProfile
from .registry import RightsRegistry
from .compatibility import Compatible, check_compatible
from .dominance import DominanceChecker
from .opportunity_cost import OpportunityCost, compute_opportunity_cost

__all__ = [
    "RightsBundle",
    "RightsStateRecord",
    "ODRLProfile",
    "RightsRegistry",
    "Compatible",
    "check_compatible",
    "DominanceChecker",
    "OpportunityCost",
    "compute_opportunity_cost",
]
