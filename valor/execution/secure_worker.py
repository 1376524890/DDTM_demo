"""Isolated worker entrypoint for controlled training (P0-M/P0-N).

The worker receives a protected dataset path and a serialized TrainingJobSpec.
It never receives an in-memory Python object from the orchestrator.
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd


def run_worker(data_path: str, job_json: str) -> dict:
    from valor.core.hashing import content_hash
    from valor.valuation.mnist_trainer import train_mnist_mlp

    data = np.load(data_path)
    X = data["X"]
    y = data["y"]
    job = json.loads(job_json)

    Xdf = pd.DataFrame(np.asarray(X, dtype=np.float32))
    ydf = pd.Series(np.asarray(y, dtype=np.int64))
    n = len(Xdf)
    split = int(n * 0.8)
    X_tr, y_tr = Xdf.iloc[:split], ydf.iloc[:split]
    X_te, y_te = Xdf.iloc[split:], ydf.iloc[split:]

    result = train_mnist_mlp(
        X_tr, y_tr, X_te, y_te,
        epochs=int(job["hyperparameters"].get("epochs", 5)),
        batch_size=int(job["hyperparameters"].get("batch_size", 256)),
        lr=float(job["hyperparameters"].get("lr", 1e-3)),
        seed=int(job.get("seed", 0)),
    )
    model = result["model"]
    acc = result["test_acc"]
    train_loss = result["train_loss"]

    import torch

    model._nn.eval()
    Xe = model.to_tensor(X_te)
    yte = torch.tensor(ydf.iloc[split:].to_numpy(dtype=np.int64))
    with torch.no_grad():
        logits = model._nn(Xe)
        pred_te = logits.argmax(dim=1).numpy()
        eval_loss = float(torch.nn.functional.cross_entropy(logits, yte).item())
    train_acc = 1.0 - min(train_loss, 1.0)
    model_hash = content_hash({
        "job": job.get("job_spec_hash", ""),
        "test_acc": round(acc, 6),
    })
    return {
        "metrics": {
            "train_loss": train_loss, "eval_loss": eval_loss,
            "accuracy": acc, "train_accuracy": train_acc,
            "n_train": int(len(X_tr)), "n_eval": int(len(X_te)),
        },
        "model_artifact_hash": model_hash,
        "worker_pid": __import__("os").getpid(),
    }


def main() -> int:
    data_path, job_json = sys.argv[1], sys.argv[2]
    out = run_worker(data_path, job_json)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
