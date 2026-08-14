"""价格边界可视化（Phase 8）。"""

from __future__ import annotations

from pathlib import Path


def plot_price_bounds(p_max: float, p_min: float, decision: str, out: str) -> str:
    """绘制 P_max / P_min 边界图，保存到 out，返回路径。"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 2.2))
    ax.barh([0], [p_max], left=[min(p_min, 0)], color="green", alpha=0.5)
    ax.barh([0], [max(p_min - min(p_min, 0), 0)], color="orange", alpha=0.5)
    ax.axvline(p_min, color="red", linestyle="--", label=f"P_min={p_min:.1f}")
    ax.axvline(p_max, color="blue", linestyle="--", label=f"P_max={p_max:.1f}")
    ax.set_yticks([])
    ax.set_title(f"Trade Margin: {decision} (M={p_max - p_min:.1f})")
    ax.legend()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out
