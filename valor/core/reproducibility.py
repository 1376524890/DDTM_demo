"""Reproducibility 元数据（检查单 P）。

每次 run 生成机器可读 JSON，至少包含：
    valor_version / git_commit / git_dirty / python_version / platform /
    dependency_lock_hash / config_hash / schema_version / timestamp_utc

要求：
- git commit 可获取；dirty 工作树不会伪报 clean
- timestamp 使用 UTC；元数据自身可序列化
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

from .. import __version__
from .canonical_json import CANONICAL_SCHEMA_VERSION, canonical_dumps
from .hashing import sha256_hex

# 记录版本哈希的关键依赖（对齐 pyproject 依赖声明）
_TRACKED_DEPENDENCIES = (
    "numpy",
    "pandas",
    "scipy",
    "scikit-learn",
    "pydantic",
    "fastapi",
    "uvicorn",
    "httpx",
    "cryptography",
    "networkx",
    "matplotlib",
    "cleanlab",
)


def git_commit(repo_root: str = ".") -> str | None:
    """读取当前 HEAD 完整哈希；失败返回 None。"""
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        return out.stdout.strip() or None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def git_dirty(repo_root: str = ".") -> bool:
    """检查工作树是否 dirty（porcelain 非空即 dirty）。"""
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "status", "--porcelain"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        return out.stdout.strip() != ""
    except (FileNotFoundError, subprocess.SubprocessError):
        return True  # 无法确认时保守视为 dirty


def _pkg_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return ""


def dependency_lock_hash() -> str:
    """对关键依赖的已安装版本做确定性哈希，反映依赖锁变化。"""
    versions = {name: _pkg_version(name) for name in _TRACKED_DEPENDENCIES}
    blob = canonical_dumps(versions).encode("utf-8")
    return sha256_hex(blob)


def build_repro_metadata(
    config_hash: str | None = None,
    repo_root: str = ".",
) -> dict[str, Any]:
    """组装完整 reproducibility 元数据字典（自身可 canonicalize/序列化）。"""
    return {
        "valor_version": __version__,
        "git_commit": git_commit(repo_root),
        "git_dirty": git_dirty(repo_root),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "dependency_lock_hash": dependency_lock_hash(),
        "config_hash": config_hash,
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def build_repro_json(config_hash: str | None = None) -> str:
    """返回可读 JSON 字符串（用于日志/报告）。"""
    return json.dumps(
        build_repro_metadata(config_hash=config_hash),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
