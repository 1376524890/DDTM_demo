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


class InvalidSchemaError(VALORError):
    """配置/对象 schema 非法（检查单 M INVALID_SCHEMA）。"""

    code = "INVALID_SCHEMA"


class InvalidHashError(VALORError):
    """哈希格式非法（长度/字符不符合要求，检查单 M/D INVALID_HASH）。"""

    code = "INVALID_HASH"


class InvalidIDError(VALORError):
    """ID 格式非法（检查单 E/M INVALID_ID）。"""

    code = "INVALID_ID"


class CanonicalizationError(VALORError):
    """canonical 序列化遇到不支持/不确定类型（检查单 M CANONICALIZATION_ERROR）。"""

    code = "CANONICALIZATION_ERROR"


class InvalidRightsError(VALORError):
    """权利束字段非法 / 相互矛盾（检查单 M/K INVALID_RIGHTS）。"""

    code = "INVALID_RIGHTS"


class ConfigVersionUnsupportedError(VALORError):
    """配置 schema 版本不受支持（检查单 M/I CONFIG_VERSION_UNSUPPORTED）。"""

    code = "CONFIG_VERSION_UNSUPPORTED"


class InvalidSourceKindError(VALORError):
    """参数来源类型非法 / 与当前模式冲突（检查单 B2 INVALID_SOURCE_KIND）。"""

    code = "INVALID_SOURCE_KIND"


class InvalidSourceRefError(VALORError):
    """参数证据引用 source_ref 格式/方案非法（检查单 O）。"""

    code = "INVALID_SOURCE_REF"


class ParameterConflictError(VALORError):
    """同名参数来源/单位/值冲突（检查单 Q#20/#21）。"""

    code = "PARAMETER_CONFLICT"


# 便于按 code 字符串引用的别名（对齐规范 §5.3 返回文本）
UNRESOLVED_PARAMETER = "UNRESOLVED_PARAMETER"
OUT_OF_CERTIFIED_RANGE = "OUT_OF_CERTIFIED_RANGE"
MISSING_EVIDENCE_REF = "MISSING_EVIDENCE_REF"
UNIT_MISMATCH = "UNIT_MISMATCH"
PROFILE_OUT_OF_CERTIFIED_RANGE = "PROFILE_OUT_OF_CERTIFIED_RANGE"
INFEASIBLE_SECURITY = "INFEASIBLE_SECURITY"
COUNTERFACTUAL_INFEASIBLE = "COUNTERFACTUAL_INFEASIBLE"
INVALID_SCHEMA = "INVALID_SCHEMA"
INVALID_HASH = "INVALID_HASH"
INVALID_ID = "INVALID_ID"
CANONICALIZATION_ERROR = "CANONICALIZATION_ERROR"
INVALID_RIGHTS = "INVALID_RIGHTS"
CONFIG_VERSION_UNSUPPORTED = "CONFIG_VERSION_UNSUPPORTED"
INVALID_SOURCE_KIND = "INVALID_SOURCE_KIND"
INVALID_SOURCE_REF = "INVALID_SOURCE_REF"
PARAMETER_CONFLICT = "PARAMETER_CONFLICT"
