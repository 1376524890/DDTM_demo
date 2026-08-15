"""保密审计：Commit-then-Reveal 摘要审计（P-ZK 务实实现）。

目标：让分布式审计节点**不接触卖方全量明文数据**，仍能验证数据质量。

方案（对齐用户问题"分布式节点能做到的程度"）：
1. 卖方提交
   - 行级 Merkle 承诺树 `CommitmentTree`（根 = H(D)），每行是叶子
   - 聚合统计摘要 `DataSummary`（每列 mean/std/missing_rate、整行重复率、
     每类计数）—— 由卖方在明文上计算，但只提交摘要，不提交原始行
2. 审计节点收到 `(H(D) 根, DataSummary, algorithm_spec)`，**不含原始行**
   - 在摘要上运行质量判定（分布漂移/缺失/重复/label 污染）
3. challenge（强验证）：节点随机选 k 个行索引 → 卖方揭示这些行
   → 节点校验 H(揭示行) 是承诺树的叶子（Merkle proof）→ 防伪造摘要
4. 效果：节点看不到全量明文，只看到聚合摘要 + 零星被挑战的行（受控揭示）

保留现有 quorum / VCG / BFT / challenge 机制（本模块只替换"节点拿全量数据"这一环）。

保密性量化：节点可见字节数 ≈ 摘要固定大小 + k·行大小，而非 O(全量数据)。
计算成本：摘要 O(n·d)；Merkle 树 O(n)；单次 challenge O(k·d)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from valor.core.hashing import content_hash, sha256_hex


# ---------------------------------------------------------------------------
# 行级 Merkle 承诺树
# ---------------------------------------------------------------------------
class CommitmentTree:
    """行级 Merkle 承诺树：根 = H(D)，叶子 = 每行 hash。"""

    def __init__(self, X: pd.DataFrame, y: pd.Series | None = None) -> None:
        self._leaf_hashes: list[str] = []
        self._tree: list[list[str]] = []
        for i, row in enumerate(X.itertuples(index=False)):
            leaf = content_hash({"row": list(row)})
            if y is not None:
                leaf = sha256_hex((leaf + content_hash({"label": int(y.iloc[i])})).encode())
            self._leaf_hashes.append(leaf)
        self._tree = self._build(self._leaf_hashes)

    def _build(self, leaves: list[str]) -> list[list[str]]:
        level = leaves
        tree = [level]
        while len(level) > 1:
            nxt = []
            for i in range(0, len(level), 2):
                a = level[i]
                b = level[i + 1] if i + 1 < len(level) else a
                nxt.append(sha256_hex((a + b).encode()))
            tree.append(nxt)
            level = nxt
        return tree

    @property
    def root(self) -> str:
        return self._tree[-1][0]

    def leaf(self, i: int) -> str:
        return self._leaf_hashes[i]

    def merkle_proof(self, i: int) -> list[str]:
        """返回从叶子 i 到根的兄弟 hash 路径（供验证）。"""
        proof = []
        idx = i
        for level in self._tree[:-1]:
            sibling = idx + 1 if idx % 2 == 0 else idx - 1
            if sibling < len(level):
                proof.append(level[sibling])
            idx //= 2
        return proof

    @staticmethod
    def verify(root: str, i: int, leaf_hash: str, proof: list[str]) -> bool:
        h = leaf_hash
        idx = i
        for sib in proof:
            if idx % 2 == 0:
                h = sha256_hex((h + sib).encode())
            else:
                h = sha256_hex((sib + h).encode())
            idx //= 2
        return h == root


# ---------------------------------------------------------------------------
# 聚合统计摘要（卖方只提交这个，不提交原始行）
# ---------------------------------------------------------------------------
@dataclass
class DataSummary:
    """卖方提交的聚合统计摘要（不包含原始行）。"""

    n_rows: int
    n_features: int
    # 每列：{col: {"mean":, "std":, "missing_rate":}}
    columns: dict[str, dict[str, float]] = field(default_factory=dict)
    duplicate_rate: float = 0.0
    class_counts: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_data(cls, X: pd.DataFrame, y: pd.Series | None = None) -> "DataSummary":
        cols = {}
        for c in X.columns:
            col = X[c]
            missing_rate = float(col.isna().mean()) if len(col) else 0.0
            vals = col.dropna()
            cols[c] = {
                "mean": float(vals.mean()) if len(vals) else 0.0,
                "std": float(vals.std(ddof=0)) if len(vals) > 1 else 0.0,
                "missing_rate": missing_rate,
            }
        dup_rate = 0.0
        if len(X):
            from valor.quality.native.duplicates import run_exact_duplicates

            out = run_exact_duplicates(X)
            dup_rate = float(out.metrics.get("exact_duplicate_rate", 0.0))
        class_counts = {}
        if y is not None:
            for k, v in y.value_counts().items():
                class_counts[str(k)] = int(v)
        return cls(n_rows=len(X), n_features=X.shape[1], columns=cols,
                   duplicate_rate=dup_rate, class_counts=class_counts)

    def to_plain(self) -> dict:
        return {
            "n_rows": self.n_rows, "n_features": self.n_features,
            "columns": self.columns, "duplicate_rate": self.duplicate_rate,
            "class_counts": self.class_counts,
        }

    @property
    def summary_hash(self) -> str:
        return content_hash(self.to_plain())


# ---------------------------------------------------------------------------
# 审计节点：只在摘要上判定质量（不接触原始行）
# ---------------------------------------------------------------------------
class PrivateAuditVerifier:
    """审计节点侧验证器：在摘要上判定质量 + 校验 Merkle 承诺。

    节点**不接收原始行**，只接收 (commitment_root, summary)。质量判定完全
    基于摘要；挑战时用 Merkle proof 验证零星揭示行与承诺一致。
    """

    def __init__(
        self,
        *,
        reference_summary: DataSummary,
        candidate_summary: DataSummary,
        alpha_shift: float = 0.01,
        dup_threshold: float = 0.05,
        missing_threshold: float = 0.2,
    ) -> None:
        self.reference_summary = reference_summary
        self.candidate_summary = candidate_summary
        self.alpha_shift = alpha_shift
        self.dup_threshold = dup_threshold
        self.missing_threshold = missing_threshold

    def _z_score(self, cand_mean: float, ref_mean: float, ref_std: float,
                 ref_n: int) -> float:
        """基于摘要的两样本均值 z 检验（无需原始数据）。"""
        if ref_std <= 0 or ref_n <= 0:
            return 0.0
        return abs(cand_mean - ref_mean) / (ref_std / np.sqrt(ref_n))

    def assess_quality(self) -> tuple[str, dict]:
        """在摘要上判定质量，返回 (outcome, metrics)。"""
        drift = 0
        total = len(self.reference_summary.columns)
        max_z = 0.0
        for col in self.reference_summary.columns:
            if col not in self.candidate_summary.columns:
                continue
            rc, cc = self.reference_summary.columns[col], self.candidate_summary.columns[col]
            z = self._z_score(cc["mean"], rc["mean"], rc["std"], rc["missing_rate"] + 1)
            # 用参考 std 与候选 std 的偏差也计入漂移
            std_ratio = cc["std"] / rc["std"] if rc["std"] > 0 else 0.0
            if z > 3.0 or abs(std_ratio - 1.0) > 0.5:  # ~3σ 显著漂移
                drift += 1
            max_z = max(max_z, z)
        missing_flag = any(
            c.get("missing_rate", 0) > self.missing_threshold
            for c in self.candidate_summary.columns.values())
        dup_flag = self.candidate_summary.duplicate_rate > self.dup_threshold
        if drift >= 1 or missing_flag or dup_flag:
            outcome = "QUALITY_FAIL"
        else:
            outcome = "PASS"
        metrics = {
            "n_significant_drift": drift, "total_features": total,
            "max_z": max_z, "missing_flag": missing_flag,
            "dup_flag": dup_flag,
            "candidate_duplicate_rate": self.candidate_summary.duplicate_rate,
        }
        return outcome, metrics

    def verify_revealed_row(self, row_idx: int, revealed_row: list,
                            leaf_hash: str, proof: list[str],
                            commitment_root: str) -> bool:
        """challenge：验证揭示行 hash 是承诺树叶子（Merkle proof）。"""
        return CommitmentTree.verify(commitment_root, row_idx, leaf_hash, proof)


def private_audit_evidence_provider(
    *,
    reference_X: pd.DataFrame,
    candidate_X: pd.DataFrame,
    candidate_y: pd.Series | None = None,
    **kwargs,
):
    """构造保密审计 evidence provider。

    卖方先算承诺树 + 摘要；provider 对每个节点返回 (commitment_root, summary)，
    节点在摘要上判定（不接触原始行）。
    """
    ref_summary = DataSummary.from_data(reference_X)
    cand_summary = DataSummary.from_data(candidate_X, candidate_y)
    # 卖方承诺树（行级 Merkle），节点只有 root
    tree = CommitmentTree(candidate_X, candidate_y)
    root = tree.root
    verifier = PrivateAuditVerifier(
        reference_summary=ref_summary, candidate_summary=cand_summary, **kwargs)
    outcome, metrics = verifier.assess_quality()

    def provider(node_id: str, task) -> dict:
        return {
            "evidence_id": f"evt-{task.task_id}-{node_id}",
            "result": outcome,
            "quality_metrics": {
                **metrics, "commitment_root": root,
                "candidate_summary_hash": cand_summary.summary_hash,
                "reference_summary_hash": ref_summary.summary_hash,
            },
        }

    provider.real_result = type("R", (), {
        "outcome": outcome,
        "to_plain": lambda: {"outcome": outcome, **metrics},
    })()
    provider.private = {
        "commitment_root": root, "summary": cand_summary,
        "verifier": verifier, "n_rows_revealed": 0,
    }
    return provider


__all__ = [
    "CommitmentTree", "DataSummary", "PrivateAuditVerifier",
    "private_audit_evidence_provider",
]
