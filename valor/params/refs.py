"""source_ref 证据引用统一 schema（检查单 O）。

为每个参数来源规定合法引用方案，保证以后能回答"这个数字究竟从哪里来"：
    OBSERVED_DATA     → dataset://<artifact_hash>[@version]
    CALIBRATED        → calib://<calibration_run_id>[@version]
    CONTRACT_INPUT    → contract://<contract_id>
    MARKET_DISCOVERED → market://<auction/bid_id>
    OPTIMIZER_OUTPUT  → optimizer://<optimization_run_id>
    THREAT_SCENARIO   → threat://<scenario_manifest_id>
    STANDARD_CONSTANT → standard://<constant_name>
    TEST_FIXTURE      → fixture://<fixture_id>

Phase 0 不需要真正生成这些 artifact，但 reference contract 必须先定义。
"""

from __future__ import annotations

import re

from valor.core.enums import ParamSource
from valor.core.errors import InvalidSourceRefError, MissingEvidenceRefError

# 各来源允许的 URI scheme
REF_SCHEMES: dict[ParamSource, str] = {
    ParamSource.OBSERVED_DATA: "dataset",
    ParamSource.CALIBRATED: "calib",
    ParamSource.CONTRACT_INPUT: "contract",
    ParamSource.MARKET_DISCOVERED: "market",
    ParamSource.OPTIMIZER_OUTPUT: "optimizer",
    ParamSource.THREAT_SCENARIO: "threat",
    ParamSource.STANDARD_CONSTANT: "standard",
    ParamSource.TEST_FIXTURE: "fixture",
}

# 通用 URI 模式：<scheme>://<artifact>[@version]
_URI_RE = re.compile(r"^[a-z0-9]+://[A-Za-z0-9/._:@\-]+$")


def validate_source_ref(ref: str, source_kind: ParamSource) -> str:
    """校验 source_ref 的格式与 scheme 是否匹配来源类型。

    - 空字符串/缺失 → MISSING_EVIDENCE_REF
    - 非 URI 格式 / scheme 与来源不符 → INVALID_SOURCE_REF
    """
    if not isinstance(ref, str) or not ref.strip():
        raise MissingEvidenceRefError(
            f"[{source_kind.value}] 缺少证据引用 source_ref（MISSING_EVIDENCE_REF）"
        )
    if not _URI_RE.match(ref):
        raise InvalidSourceRefError(f"非法 source_ref 格式: {ref!r}")
    scheme = ref.split("://", 1)[0]
    expected = REF_SCHEMES[source_kind]
    if scheme != expected:
        raise InvalidSourceRefError(
            f"source_ref scheme 与来源不匹配: {ref!r}，"
            f"{source_kind.value} 期望 scheme={expected!r}"
        )
    return ref
