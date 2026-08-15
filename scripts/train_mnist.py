#!/usr/bin/env python3
"""在本地 MNIST 上训练 MLP（经 7891 代理下载，data/raw/mnist/）。

用法：python scripts/train_mnist.py [--epochs N] [--max-samples M]
"""

from __future__ import annotations

import argparse
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MNIST MLP 训练")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--max-samples", type=int, default=None,
                    help="只取前 N 训练样本（快速跑通）")
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args(argv)

    from valor.data.download import load_dataset
    from valor.valuation.mnist_trainer import train_mnist_mlp

    print("加载 MNIST（本地缓存）...")
    train = load_dataset("mnist")
    # 用 sklearn 内置 digits 作为测试集划分（真实 MNIST 的 t10k 单独读）
    from valor.data.download import _BUILTIN  # noqa: F401
    import gzip
    import numpy as np
    import pandas as pd

    base = __import__("pathlib").Path("data/raw/mnist")
    def load_idx(name):
        with gzip.open(base / name, "rb") as f:
            d = f.read()
        magic = int.from_bytes(d[:4], "big")
        if magic == 2051:
            n = int.from_bytes(d[4:8], "big"); r = int.from_bytes(d[8:12], "big"); c = int.from_bytes(d[12:16], "big")
            return np.frombuffer(d[16:], dtype=np.uint8).reshape(n, r * c)
        n = int.from_bytes(d[4:8], "big"); return np.frombuffer(d[8:], dtype=np.uint8)
    Xte = pd.DataFrame(load_idx("t10k-images-idx3-ubyte.gz"))
    yte = pd.Series(load_idx("t10k-labels-idx1-ubyte.gz"))

    print(f"训练集 {train.X.shape}，测试集 {Xte.shape}")
    res = train_mnist_mlp(
        train.X, train.y, Xte, yte,
        epochs=args.epochs, max_samples=args.max_samples, lr=args.lr,
    )
    print(f"训练完成: test_acc={res['test_acc']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
