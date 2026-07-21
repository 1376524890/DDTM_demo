#!/usr/bin/env python3
"""Train the public 128-64-1 architecture and export Q16.16 parameters.

The output JSON is deserialized directly by the Rust tee-evaluator as Model:
{
  "w1": [[int32; 128]; 64],
  "b1": [int32; 64],
  "w2": [int32; 64],
  "b2": int32
}
All values are Q16.16 fixed-point integers.
"""
from __future__ import annotations
import argparse, json, random
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class HingeMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(128, 64)
        self.fc2 = nn.Linear(64, 1)

    def forward(self, x):
        return self.fc2(torch.relu(self.fc1(x))).squeeze(-1)


def quantize_q16(t: torch.Tensor) -> list:
    """Quantize tensor to Q16.16 int32 values."""
    a = torch.round(t.detach().cpu() * 65536.0).to(torch.int64).numpy()
    if (a < np.iinfo(np.int32).min).any() or (a > np.iinfo(np.int32).max).any():
        raise ValueError("parameter Q16.16 overflow beyond int32")
    return a.astype(np.int32).tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--validation", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260721)
    ap.add_argument("--device", default="cuda:0")
    args = ap.parse_args()

    # Deterministic training.
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    torch.use_deterministic_algorithms(True, warn_only=True)

    base = np.load(args.base)
    val = np.load(args.validation)
    xb = torch.from_numpy(base["x"]).float()
    yb = torch.from_numpy(base["y"].astype(np.float32))
    xv = torch.from_numpy(val["x"]).float()
    yv = torch.from_numpy(val["y"].astype(np.float32))

    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    model = HingeMLP().to(device)
    opt = torch.optim.SGD(model.parameters(), lr=0.01, momentum=0.0, weight_decay=1e-4)

    loader = DataLoader(
        TensorDataset(xb, yb),
        batch_size=1024,
        shuffle=True,
        generator=torch.Generator().manual_seed(args.seed),
        num_workers=0,
    )

    best = None
    for epoch in range(args.epochs):
        model.train()
        for x, y in loader:
            x = x.to(device)
            y = y.to(device)
            opt.zero_grad(set_to_none=True)
            out = model(x)
            loss = torch.relu(1.0 - y * out).mean()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()

        model.eval()
        with torch.no_grad():
            score = model(xv.to(device))
            val_loss = torch.relu(1.0 - yv.to(device) * score).mean().item()
            acc = ((score >= 0).float() * 2 - 1 == yv.to(device)).float().mean().item()

        if best is None or val_loss < best[0]:
            best = (val_loss, acc, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()})

        print(json.dumps({"epoch": epoch, "val_hinge": val_loss, "val_accuracy": acc}))

    # Load best parameters.
    model.load_state_dict(best[2])

    # Export in format matching Rust Model struct.
    # w1: [64][128] int32 (Q16.16)
    # b1: [64] int32 (Q16.16)
    # w2: [64] int32 (Q16.16)
    # b2: int32 (Q16.16)
    export = {
        "w1": quantize_q16(model.fc1.weight),       # shape [64, 128]
        "b1": quantize_q16(model.fc1.bias),          # shape [64]
        "w2": quantize_q16(model.fc2.weight.squeeze(0)),  # shape [64]
        "b2": int(quantize_q16(model.fc2.bias.squeeze(0))[0]),  # scalar
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(export, indent=2), encoding="utf-8")

    print(json.dumps({
        "best_val_hinge": best[0],
        "best_val_accuracy": best[1],
        "output": str(args.output),
    }))


if __name__ == "__main__":
    main()
