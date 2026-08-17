"""P0-M/P0-N 受控训练测试：合法训练真实运行 + 非法训练在 key release 前被拒。"""

from __future__ import annotations

import numpy as np
import pytest

from valor.execution.controlled_training import ControlledTrainingRunner, OutputPolicy
from valor.execution.secure_execution import (
    TrainingJobSpec,
    default_mnist_catalog,
)
from valor.usage.models import UsageState


def _data(n=600):
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, size=(n, 784), dtype=np.uint8), \
        rng.integers(0, 10, size=n)


def _job(actor="buyer_org_A", purpose="digit-classification",
         requested_output="MODEL_ARTIFACT", algorithm="MNIST_MLP_TRAIN",
         hyperparams=None, image="sha256:mnist-mlp-train-container"):
    return TrainingJobSpec(
        job_id="job-1", tx_id="tx-1",
        dataset_commitment_hash="d" * 64, rights_hash="r" * 64,
        actor_id=actor, declared_purpose=purpose,
        algorithm_id=algorithm, algorithm_hash="h" * 64,
        container_image_digest=image,
        hyperparameters=hyperparams or {"epochs": 2, "batch_size": 128, "lr": 1e-3},
        hyperparameters_hash="hp" * 32,
        input_refs=["d" * 64], requested_output=requested_output,
        execution_profile_id="ep-1", network_policy_hash="np" * 32, seed=0,
    )


def _rights(access_mode="COMPUTE_ONLY", derivative=True, q=3):
    return type("R", (), {
        "t0": "2026-01-01", "t1": "2026-12-31", "q": q,
        "purposes": frozenset(["digit-classification"]),
        "scope": "buyer_org_A", "exclusivity": False,
        "redistribution": False, "derivative": derivative,
        "access_mode": access_mode,
    })()


def test_legal_training_runs():
    """合法训练真实执行，生成 metrics + model hash。"""
    X, y = _data(600)
    cat = default_mnist_catalog()
    # 算法 code_hash 需匹配目录
    job = _job()
    job.algorithm_hash = cat.get("MNIST_MLP_TRAIN").code_hash
    job.container_image_digest = cat.get("MNIST_MLP_TRAIN").container_digest
    runner = ControlledTrainingRunner(catalog=cat, rights=_rights())
    state = UsageState()
    out = runner.run(
        job=job, dataset_X=X, dataset_y=y,
        valid_from="2026-01-01", valid_until="2026-12-31", max_uses=3,
        purposes=frozenset(["digit-classification"]),
        authorized_actors={"buyer_org_A"},
        allowed_environments={"approved_compute"},
        environment="approved_compute",
        access_mode="COMPUTE_ONLY", derivative=True,
        usage_state=state, timestamp="2026-03-01",
    )
    assert out.decision == "ALLOW"
    assert out.training_started is True
    assert out.model_created is True
    assert out.key_released is True
    assert out.raw_data_access is False  # buyer 不接触 raw data
    assert "accuracy" in out.metrics and "eval_loss" in out.metrics
    assert out.model_artifact_hash


def test_illegal_actor_denied():
    """U1 unauthorized actor → DENY 在 key release 前。"""
    X, y = _data(200)
    cat = default_mnist_catalog()
    job = _job(actor="buyer_org_B")
    job.algorithm_hash = cat.get("MNIST_MLP_TRAIN").code_hash
    job.container_image_digest = cat.get("MNIST_MLP_TRAIN").container_digest
    runner = ControlledTrainingRunner(catalog=cat)
    out = runner.run(
        job=job, dataset_X=X, dataset_y=y,
        valid_from="2026-01-01", valid_until="2026-12-31", max_uses=3,
        purposes=frozenset(["digit-classification"]),
        authorized_actors={"buyer_org_A"},
        allowed_environments={"approved_compute"},
        environment="approved_compute",
        access_mode="COMPUTE_ONLY", derivative=True,
        usage_state=UsageState(), timestamp="2026-03-01",
    )
    assert out.decision == "DENY"
    assert out.key_released is False
    assert out.raw_data_access is False
    assert out.training_started is False
    assert out.model_created is False


def test_illegal_purpose_and_output_denied():
    """U2 unauthorized purpose + U7 derivative=False but MODEL_ARTIFACT。"""
    X, y = _data(200)
    cat = default_mnist_catalog()
    # U2
    job = _job(purpose="marketing")
    job.algorithm_hash = cat.get("MNIST_MLP_TRAIN").code_hash
    job.container_image_digest = cat.get("MNIST_MLP_TRAIN").container_digest
    runner = ControlledTrainingRunner(catalog=cat)
    out = runner.run(
        job=job, dataset_X=X, dataset_y=y,
        valid_from="2026-01-01", valid_until="2026-12-31", max_uses=3,
        purposes=frozenset(["digit-classification"]),
        authorized_actors={"buyer_org_A"},
        allowed_environments={"approved_compute"},
        environment="approved_compute",
        access_mode="COMPUTE_ONLY", derivative=True,
        usage_state=UsageState(), timestamp="2026-03-01",
    )
    assert out.decision == "DENY" and out.training_started is False
    # U7 derivative=False but MODEL_ARTIFACT
    job2 = _job()
    job2.algorithm_hash = cat.get("MNIST_MLP_TRAIN").code_hash
    job2.container_image_digest = cat.get("MNIST_MLP_TRAIN").container_digest
    out2 = runner.run(
        job=job2, dataset_X=X, dataset_y=y,
        valid_from="2026-01-01", valid_until="2026-12-31", max_uses=3,
        purposes=frozenset(["digit-classification"]),
        authorized_actors={"buyer_org_A"},
        allowed_environments={"approved_compute"},
        environment="approved_compute",
        access_mode="COMPUTE_ONLY", derivative=False,
        usage_state=UsageState(), timestamp="2026-03-01",
    )
    assert out2.decision == "DENY" and out2.training_started is False


def test_unauthorized_algorithm_and_container():
    """U5/U6 unauthorized algorithm/container → DENY。"""
    X, y = _data(200)
    cat = default_mnist_catalog()
    runner = ControlledTrainingRunner(catalog=cat)
    # U5 wrong algorithm hash
    job = _job()
    job.algorithm_hash = "wrong" * 32
    job.container_image_digest = cat.get("MNIST_MLP_TRAIN").container_digest
    out = runner.run(
        job=job, dataset_X=X, dataset_y=y,
        valid_from="2026-01-01", valid_until="2026-12-31", max_uses=3,
        purposes=frozenset(["digit-classification"]),
        authorized_actors={"buyer_org_A"},
        allowed_environments={"approved_compute"},
        environment="approved_compute",
        access_mode="COMPUTE_ONLY", derivative=True,
        usage_state=UsageState(), timestamp="2026-03-01",
    )
    assert out.decision == "DENY" and out.training_started is False


def test_output_policy_raw_export_denied():
    """U8 COMPUTE_ONLY but RAW_EXPORT → DENY。"""
    assert OutputPolicy.allowed(requested="RAW_EXPORT",
                                access_mode="COMPUTE_ONLY", derivative=True) is False
    assert OutputPolicy.allowed(requested="MODEL_ARTIFACT",
                                access_mode="COMPUTE_ONLY", derivative=True) is True
    assert OutputPolicy.allowed(requested="MODEL_ARTIFACT",
                                access_mode="COMPUTE_ONLY", derivative=False) is False
