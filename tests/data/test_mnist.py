"""本地 MNIST 加载与训练器测试（经 7891 代理下载，data/raw/mnist/）。"""

from __future__ import annotations

import pytest

from valor.data.download import load_dataset


@pytest.fixture(scope="module")
def mnist():
    return load_dataset("mnist")


def test_mnist_shape(mnist):
    # 60000×784，10 类
    assert mnist.X.shape == (60000, 784)
    assert mnist.y.shape == (60000,)
    assert set(mnist.y.unique()) == set(range(10))


def test_mnist_pixel_range(mnist):
    assert mnist.X.values.min() >= 0
    assert mnist.X.values.max() <= 255


def test_mnist_trainer_small():
    """小规模快速训练跑通（torch MLP）。"""
    from valor.valuation.mnist_trainer import train_mnist_mlp

    train = load_dataset("mnist")
    Xtr = train.X.iloc[:300]
    ytr = train.y.iloc[:300]
    Xte = train.X.iloc[::20]  # 抽样测试
    yte = train.y.iloc[::20]
    res = train_mnist_mlp(Xtr, ytr, Xte, yte, epochs=1, max_samples=300)
    assert "test_acc" in res
    assert 0.0 <= res["test_acc"] <= 1.0
