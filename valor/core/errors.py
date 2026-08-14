"""VALOR 错误层级（fail-closed 语义）。

对齐规范：
- §5.3 Fail-Closed：ResolveAll 失败返回
  UNRESOLVED_PARAMETER / OUT_OF_CERTIFIED_RANGE / MISSING_EVIDENCE_REF / UNIT_MISMATCH
- §22 PROFILE_OUT_OF_CERTIFIED_RANGE
- §30 INFEASIBLE_SECURITY
- §18 COUNTERFACTUAL_INFEASIBLE
"""

from __future__ import annotations


class VALORError(Exception):
    """VALOR 所有自定义异常基类。"""

    code: str = "VALOR_ERROR"

    def __init__(self, message: str, *, detail: object = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def to_plain(self) -> dict:
        """转为 JSON 原生字典，便于写入日志/结果。"""
        return {"code": self.code, "message": self.message}


class UnresolvedParameterError(VALORError):
    """参数无法解析来源（规范 §5.3 UNRESOLVED_PARAMETER）。"""

    code = "UNRESOLVED_PARAMETER"


class OutOfCertifiedRangeError(VALORError):
    """参数超出认证范围（规范 §5.3 OUT_OF_CERTIFIED_RANGE）。"""

    code = "OUT_OF_CERTIFIED_RANGE"


class MissingEvidenceRefError(VALORError):
    """缺少证据引用（规范 §5.3 MISSING_EVIDENCE_REF）。"""

    code = "MISSING_EVIDENCE_REF"


class UnitMismatchError(VALORError):
    """单位不一致（规范 §5.3 UNIT_MISMATCH）。"""

    code = "UNIT_MISMATCH"


class ProfileOutOfCertifiedRangeError(VALORError):
    """输入不属于任何认证 cell（规范 §22 PROFILE_OUT_OF_CERTIFIED_RANGE）。"""

    code = "PROFILE_OUT_OF_CERTIFIED_RANGE"


class InfeasibleSecurityError(VALORError):
    """安全参数不可行（规范 §30 INFEASIBLE_SECURITY，分母关键参数为零/未解析）。"""

    code = "INFEASIBLE_SECURITY"


class CounterfactualInfeasibleError(VALORError):
    """删除 winner 后不存在可行替补委员会（规范 §18 COUNTERFACTUAL_INFEASIBLE）。"""

    code = "COUNTERFACTUAL_INFEASIBLE"


class CommitBindingError(VALORError):
    """对象绑定/承诺不一致，属确定性合同错误（规范 §4）。"""

    code = "COMMIT_BINDING"


class EntitlementError(VALORError):
    """资格/合规硬门槛失败，交易不进入价值与审计（规范 §6）。"""

    code = "ENTITLEMENT"


class ConfigError(VALORError):
    """配置缺失/非法/单位不一致（Phase 0 gate）。"""

    code = "CONFIG"


# 便于按 code 字符串引用的别名（对齐规范 §5.3 返回文本）
UNRESOLVED_PARAMETER = "UNRESOLVED_PARAMETER"
OUT_OF_CERTIFIED_RANGE = "OUT_OF_CERTIFIED_RANGE"
MISSING_EVIDENCE_REF = "MISSING_EVIDENCE_REF"
UNIT_MISMATCH = "UNIT_MISMATCH"
PROFILE_OUT_OF_CERTIFIED_RANGE = "PROFILE_OUT_OF_CERTIFIED_RANGE"
INFEASIBLE_SECURITY = "INFEASIBLE_SECURITY"
COUNTERFACTUAL_INFEASIBLE = "COUNTERFACTUAL_INFEASIBLE"
