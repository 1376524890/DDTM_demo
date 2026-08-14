"""校准/检测指标工具（规范 §66 统计规范 / §58）。"""

from __future__ import annotations


def ranking_agreement(a: list[int], b: list[int]) -> float:
    """两个 issue ranking 的一致性指标（规范 §10 Gate）。

    用 Jaccard 相似度衡量两个检出索引集合的重叠程度（0-1）。
    """
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)
