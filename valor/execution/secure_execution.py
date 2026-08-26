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


@dataclass(frozen=True)
class CapabilityToken:
    """Frozen capability token (Round 5 §22).

    A valid capability must be bound to the tx/job/dataset/rights/actor/purpose/
    algorithm/output policy/expiry/nonce. No capability, no worker start.
    """

    tx_id: str
    job_spec_hash: str
    dataset_commitment: str
    rights_hash: str
    actor: str
    purpose: str
    algorithm_hash: str
    output_policy: str
    execution_profile: str
    expiry: str
    nonce: str
    issuer: str = ""
    signature: str = ""

    @property
    def capability_hash(self) -> str:
        return content_hash({
            "tx_id": self.tx_id, "job_spec_hash": self.job_spec_hash,
            "dataset_commitment": self.dataset_commitment,
            "rights_hash": self.rights_hash, "actor": self.actor,
            "purpose": self.purpose, "algorithm_hash": self.algorithm_hash,
            "output_policy": self.output_policy,
            "execution_profile": self.execution_profile,
            "expiry": self.expiry, "nonce": self.nonce,
            "issuer": self.issuer,
        })

    def to_plain(self) -> dict:
        return {
            "tx_id": self.tx_id, "job_spec_hash": self.job_spec_hash,
            "dataset_commitment": self.dataset_commitment,
            "rights_hash": self.rights_hash, "actor": self.actor,
            "purpose": self.purpose, "algorithm_hash": self.algorithm_hash,
            "output_policy": self.output_policy,
            "execution_profile": self.execution_profile,
            "expiry": self.expiry, "nonce": self.nonce,
            "issuer": self.issuer, "signature": self.signature,
            "capability_hash": self.capability_hash,
        }



class CapabilityIssuer:
    """Issues and verifies unforgeable capability tokens (Round 6 Phase 17).

    The issuer holds an Ed25519 private key; buyers/workers receive only the
    signed token. `verify` checks signature, issuer, expiry, and single-use
    nonce replay.
    """

    def __init__(self, issuer_id: str, keypair=None) -> None:
        self.issuer_id = issuer_id
        if keypair is None:
            from valor.security.signing import SigningKeyPair
            keypair = SigningKeyPair.generate(f"cap-issuer-{issuer_id}")
        self._keypair = keypair
        self._used_nonces: set[str] = set()

    @property
    def public_key_hex(self) -> str:
        return self._keypair.public_key_hex

    def issue(self, *, tx_id, job_spec_hash, dataset_commitment, rights_hash,
              actor, purpose, algorithm_hash, output_policy, execution_profile,
              expiry, nonce) -> CapabilityToken:
        cap = CapabilityToken(
            tx_id=tx_id, job_spec_hash=job_spec_hash,
            dataset_commitment=dataset_commitment, rights_hash=rights_hash,
            actor=actor, purpose=purpose, algorithm_hash=algorithm_hash,
            output_policy=output_policy, execution_profile=execution_profile,
            expiry=expiry, nonce=nonce, issuer=self.issuer_id,
        )
        payload = self._payload(cap)
        sig = self._keypair.sign(payload).hex()
        return CapabilityToken(
            tx_id=cap.tx_id, job_spec_hash=cap.job_spec_hash,
            dataset_commitment=cap.dataset_commitment, rights_hash=cap.rights_hash,
            actor=cap.actor, purpose=cap.purpose, algorithm_hash=cap.algorithm_hash,
            output_policy=cap.output_policy, execution_profile=cap.execution_profile,
            expiry=cap.expiry, nonce=cap.nonce, issuer=cap.issuer, signature=sig,
        )

    def verify(self, capability: CapabilityToken, *, allow_replay: bool = False) -> bool:
        if capability.issuer != self.issuer_id:
            return False
        if not capability.signature:
            return False
        if capability.expiry:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            exp_str = capability.expiry.replace("Z", "+00:00")
            try:
                exp = datetime.fromisoformat(exp_str)
                if exp.tzinfo is None:
                    from datetime import timezone as _tz
                    exp = exp.replace(tzinfo=_tz.utc)
                if now > exp:
                    return False
            except ValueError:
                # date-only expiry: compare ISO date strings
                if exp_str[:10] < now.date().isoformat():
                    return False
        if not allow_replay and capability.nonce in self._used_nonces:
            return False
        if not allow_replay:
            self._used_nonces.add(capability.nonce)
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
            pub = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(self.public_key_hex))
            pub.verify(bytes.fromhex(capability.signature), self._payload(capability))
        except Exception:
            return False
        return True

    @staticmethod
    def _payload(cap: CapabilityToken) -> bytes:
        from valor.core.hashing import content_hash
        return content_hash({k: v for k, v in cap.to_plain().items()
                             if k not in ("signature",)}).encode()


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
        container_digest="LOCAL_SUBPROCESS_ARTIFACT_HASH:" + content_hash(
            {"module": "valor.execution.secure_worker", "version": "v1"}),
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
    worker_pid: int | None = None
    reason: str = ""

    def to_plain(self) -> dict:
        return {
            "decision": self.decision, "key_released": self.key_released,
            "raw_data_access": self.raw_data_access,
            "training_started": self.training_started,
            "model_created": self.model_created, "job_spec_hash": self.job_spec_hash,
            "metrics": self.metrics, "model_artifact_hash": self.model_artifact_hash,
            "worker_pid": self.worker_pid,
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
        self.issuer = CapabilityIssuer("local-cap-issuer")

    def provision_capability(self, *, job_spec_hash: str, data_ref: str,
                             key_release_decision: dict,
                             tx_id: str = "", rights_hash: str = "",
                             actor: str = "", purpose: str = "",
                             algorithm_hash: str = "", output_policy: str = "",
                             execution_profile: str = "", expiry: str = "",
                             nonce: str = "") -> dict:
        if not key_release_decision.get("allow", False):
            return {"key_released": False, "capability_ref": ""}
        cap = self.issuer.issue(
            tx_id=tx_id, job_spec_hash=job_spec_hash,
            dataset_commitment=data_ref, rights_hash=rights_hash,
            actor=actor, purpose=purpose, algorithm_hash=algorithm_hash,
            output_policy=output_policy, execution_profile=execution_profile,
            expiry=expiry, nonce=nonce,
        )
        return {"key_released": True, "capability": cap, "capability_hash": cap.capability_hash}

    def execute(self, capability, job: "TrainingJobSpec", dataset_X, dataset_y) -> dict:
        """Run certified training in a real subprocess worker.

        The orchestrator process passes a protected dataset file path and a
        serialized job spec, never an in-memory dataframe object.
        """
        import json
        import os
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        import numpy as np

        if capability is None or not getattr(capability, "capability_hash", ""):
            raise ValueError("CAPABILITY_REQUIRED: worker refused to start without a valid capability")
        if not self.issuer.verify(capability):
            raise ValueError("CAPABILITY_INVALID: worker MUST NOT start")
        if capability.job_spec_hash != job.job_spec_hash:
            raise ValueError("CAPABILITY_JOB_MISMATCH")
        if capability.dataset_commitment != job.dataset_commitment_hash:
            raise ValueError("CAPABILITY_DATASET_MISMATCH")

        repo_root = Path(__file__).resolve().parent.parent.parent
        env = dict(os.environ)
        env["PYTHONPATH"] = str(repo_root)
        with tempfile.TemporaryDirectory(prefix="valor-worker-") as td:
            data_path = os.path.join(td, "dataset.npz")
            np.savez_compressed(
                data_path,
                X=np.asarray(dataset_X, dtype=np.uint8),
                y=np.asarray(dataset_y, dtype=np.int64),
            )
            proc = subprocess.run(
                [sys.executable, "-m", "valor.execution.secure_worker",
                 data_path, json.dumps(job.to_plain())],
                capture_output=True, text=True, env=env, timeout=900,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"isolated training worker failed: {proc.stderr[-1000:]}"
                )
            return json.loads(proc.stdout.strip().splitlines()[-1])


__all__ = [
    "SecureExecutionProvider", "CapabilityToken", "CapabilityIssuer",
    "TrainingJobSpec", "TrainingOutcome",
    "CertifiedTrainingAlgorithm", "CertifiedTrainingAlgorithmCatalog",
    "default_mnist_catalog", "LocalIsolatedProvider",
]
