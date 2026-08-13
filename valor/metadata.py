"""Reproducibility 元数据：git commit / 数据集 sha256 / 参数哈希。

设计原则（机制文档 §20 复现性 + ARCHIVE_SPEC §5）：
- 每个结果文件必须可追溯到：git commit + dataset sha256 + 完整参数哈希。
- 参数哈希用确定性序列化（sorted keys），保证跨平台一致。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from typing import Any, Dict, Optional


def git_commit(repo_root: str = ".") -> Optional[str]:
    """读取当前 HEAD 的 git commit 短哈希。

    失败（如非 git 仓库）返回 None，不中断流程。
    """
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return None


def git_working_tree_clean(repo_root: str = ".") -> bool:
    """检查工作树是否干净（release 报告要求 CLEAN）。"""
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if out.returncode == 0:
            return out.stdout.strip() == ""
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return False


def file_sha256(path: str, chunk_size: int = 1 << 20) -> Optional[str]:
    """计算文件的 SHA-256（分块读取，适合大文件）。不存在返回 None。"""
    import os

    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def param_hash(config_plain: Dict[str, Any]) -> str:
    """对配置的 JSON 原生表示做确定性 SHA-256。

    使用 sort_keys=True 保证 key 顺序无关；ensure_ascii 保证编码稳定。
    """
    blob = json.dumps(
        config_plain, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def build_repro_metadata(
    config_plain: Dict[str, Any],
    dataset_sha256: Optional[str] = None,
    repo_root: str = ".",
) -> Dict[str, Any]:
    """组装完整 reproducibility 元数据字典。

    Args:
        config_plain: 配置的 JSON 原生表示（含 experiment_id/seed 等）。
        dataset_sha256: 数据集文件的 SHA-256（可选）。
        repo_root: git 仓库根目录，用于读 commit。
    """
    return {
        "git_commit": git_commit(repo_root),
        "working_tree_clean": git_working_tree_clean(repo_root),
        "dataset_sha256": dataset_sha256,
        "param_hash": param_hash(config_plain),
        "experiment_id": config_plain.get("experiment_id"),
    }
