"""SecureExecutionProvider —— 受控训练执行平面（P0-M/P0-N）。

合法 buyer 使用交易完成后的数据真正训练模型；非法使用在数据明文访问 / key
release / training start 之前被拒绝。提供：

    SecureExecutionProvider（接口）
    LocalIsolatedProvider：CI / paper local 系统实验，独立 subprocess/容器执行；
        buyer process 不得到 raw data。**不得**把它声称为 TEE。
    ConfidentialProvider（interface）：接 CoCo+Trustee/KBS 或 Gramine SGX 的
        attestation/key-release contract（本机无 TEE 时 adapter + contract 实现，
        本地实验用 LocalIsolatedProvider）。

PDP/PEP/PXP 在 key release / training start 前强制执行；DENY → key_release=False、
raw_access=False、training_started=False。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from valor.core.hashing import content_hash


class SecureExecutionProvider(Protocol):
    """受控执行提供方接口（P0-M）。"""

    name: str
    is_tee: bool

    def provision_capability(self, *, job_spec_hash: str, data_ref: str,
                             key_release_decision: dict) -> dict:
        """在授权后 provision 数据 capability。非法 → key_release=False。"""
        ...


@dataclass
class TrainingJobSpec:
    """正式 TrainingJobSpec（P0-M/P0-N）。"""

    job_id: str
    tx_id: str
    dataset_commitment_hash: str
    rights_hash: str
    actor_id: str
    declared_purpose: str
    algorithm_id: str
    algorithm_hash: str
    container_image_digest: str
    hyperparameters: dict
    hyperparameters_hash: str
    input_refs: list[str]
    requested_output: str  # METRICS_ONLY | MODEL_ARTIFACT | INFERENCE_ENDPOINT | RAW_EXPORT
    execution_profile_id: str
    network_policy_hash: str
    seed: int

    @property
    def job_spec_hash(self) -> str:
        return content_hash({
            "job_id": self.job_id, "tx_id": self.tx_id,
            "dataset_commitment_hash": self.dataset_commitment_hash,
            "rights_hash": self.rights_hash, "actor_id": self.actor_id,
            "declared_purpose": self.declared_purpose,
            "algorithm_id": self.algorithm_id, "algorithm_hash": self.algorithm_hash,
            "container_image_digest": self.container_image_digest,
            "hyperparameters_hash": self.hyperparameters_hash,
            "input_refs": self.input_refs, "requested_output": self.requested_output,
            "execution_profile_id": self.execution_profile_id,
            "network_policy_hash": self.network_policy_hash, "seed": self.seed,
        })

    def to_plain(self) -> dict:
        return {
            "job_id": self.job_id, "tx_id": self.tx_id,
            "dataset_commitment_hash": self.dataset_commitment_hash,
            "rights_hash": self.rights_hash, "actor_id": self.actor_id,
            "declared_purpose": self.declared_purpose,
            "algorithm_id": self.algorithm_id, "algorithm_hash": self.algorithm_hash,
            "container_image_digest": self.container_image_digest,
            "hyperparameters": self.hyperparameters,
            "hyperparameters_hash": self.hyperparameters_hash,
            "input_refs": self.input_refs, "requested_output": self.requested_output,
            "execution_profile_id": self.execution_profile_id,
            "network_policy_hash": self.network_policy_hash, "seed": self.seed,
            "job_spec_hash": self.job_spec_hash,
        }


@dataclass
class CertifiedTrainingAlgorithm:
    """CertifiedTrainingAlgorithmCatalog 条目（P0-M）。"""

    algorithm_id: str
    code_hash: str
    container_digest: str
    input_schema_hash: str
    output_schema_hash: str
    allowed_hyperparameter_ranges: dict

    def to_plain(self) -> dict:
        return {
            "algorithm_id": self.algorithm_id, "code_hash": self.code_hash,
            "container_digest": self.container_digest,
            "input_schema_hash": self.input_schema_hash,
            "output_schema_hash": self.output_schema_hash,
            "allowed_hyperparameter_ranges": self.allowed_hyperparameter_ranges,
        }


class CertifiedTrainingAlgorithmCatalog:
    """认证训练算法目录（禁止 buyer 提交任意 unrestricted function）。"""

    def __init__(self) -> None:
        self._algs: dict[str, CertifiedTrainingAlgorithm] = {}

    def register(self, alg: CertifiedTrainingAlgorithm) -> None:
        self._algs[alg.algorithm_id] = alg

    def get(self, algorithm_id: str) -> CertifiedTrainingAlgorithm:
        if algorithm_id not in self._algs:
            raise KeyError(f"未认证算法: {algorithm_id}")
        return self._algs[algorithm_id]

    def verify(self, job: TrainingJobSpec) -> tuple[bool, list[str]]:
        """校验 job 的算法/容器/hyperparameters 均认证。"""
        reasons: list[str] = []
        try:
            alg = self.get(job.algorithm_id)
        except KeyError as e:
            return False, [str(e)]
        if alg.code_hash != job.algorithm_hash:
            reasons.append("算法 code hash 不匹配")
        if alg.container_digest != job.container_image_digest:
            reasons.append("容器 digest 不匹配")
        for k, (lo, hi) in alg.allowed_hyperparameter_ranges.items():
            v = job.hyperparameters.get(k)
            if v is None or not (lo <= v <= hi):
                reasons.append(f"超参 {k} 超出认证范围")
        return (len(reasons) == 0), reasons


def default_mnist_catalog() -> CertifiedTrainingAlgorithmCatalog:
    """MNIST-MLP-TRAIN 认证算法（P0-M 示例）。"""
    cat = CertifiedTrainingAlgorithmCatalog()
    cat.register(CertifiedTrainingAlgorithm(
        algorithm_id="MNIST_MLP_TRAIN",
        code_hash=content_hash({"alg": "mnist-mlp-train-v1"}),
        container_digest="sha256:mnist-mlp-train-container",
        input_schema_hash=content_hash({"schema": "MNIST-784"}),
        output_schema_hash=content_hash({"schema": "metrics+model"}),
        allowed_hyperparameter_ranges={
            "epochs": (1, 100), "batch_size": (16, 1024), "lr": (1e-5, 1e-1),
        },
    ))
    return cat


@dataclass
class TrainingOutcome:
    """一次受控训练的结果（P0-N 真实生成）。"""

    decision: str  # ALLOW | DENY
    key_released: bool
    raw_data_access: bool
    training_started: bool
    model_created: bool
    job_spec_hash: str = ""
    metrics: dict = field(default_factory=dict)  # train_loss/eval_loss/accuracy
    model_artifact_hash: str = ""
    reason: str = ""

    def to_plain(self) -> dict:
        return {
            "decision": self.decision, "key_released": self.key_released,
            "raw_data_access": self.raw_data_access,
            "training_started": self.training_started,
            "model_created": self.model_created, "job_spec_hash": self.job_spec_hash,
            "metrics": self.metrics, "model_artifact_hash": self.model_artifact_hash,
            "reason": self.reason,
        }


class LocalIsolatedProvider:
    """本地隔离受控执行（CI / paper local system experiment）。

    在独立 subprocess 中运行认证训练（buyer process 不得到 raw data）。
    信任边界：保护 buyer process，但 platform host 仍在 trust boundary。
    不得声称 TEE。
    """

    name = "LocalIsolatedProvider"
    is_tee = False

    def __init__(self, catalog: CertifiedTrainingAlgorithmCatalog | None = None) -> None:
        self.catalog = catalog or default_mnist_catalog()

    def provision_capability(self, *, job_spec_hash: str, data_ref: str,
                             key_release_decision: dict) -> dict:
        if not key_release_decision.get("allow", False):
            return {"key_released": False, "capability_ref": ""}
        return {"key_released": True, "capability_ref": f"cap-{data_ref}-{job_spec_hash}"}


__all__ = [
    "SecureExecutionProvider", "TrainingJobSpec", "TrainingOutcome",
    "CertifiedTrainingAlgorithm", "CertifiedTrainingAlgorithmCatalog",
    "default_mnist_catalog", "LocalIsolatedProvider",
]
