"""可复现性元数据：钉死每一项会影响 release 报告的输入。

release 运行（``--release``）在 DIRTY 工作树上会拒绝继续，并记录 config、
optimizer 源码与数据集的 SHA-256，使报告可从一个具名提交 + 具名输入重新推导。
"""
from __future__ import annotations

import hashlib
import platform
import subprocess
from pathlib import Path
from typing import Any


def run_checked(command: list[str], cwd: Path) -> str:
    """运行一个 git 命令并返回去尾空白后的 stdout，失败则抛错。"""
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    """以 1 MiB 分块流式计算文件原始字节的 SHA-256。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_metadata(
    repository: Path,
    config_path: Path,
    optimizer_path: Path,
    dataset_path: Path | None,
    release_mode: bool,
) -> dict[str, Any]:
    """收集 git + 文件哈希 + 主机信息。

    ``release_mode`` 下 DIRTY 工作树是硬错误：正式报告必须可由一个具名提交重现，
    这要求工作树干净。

    ``dataset_path`` 可为 ``None``——G0 是解析实验，无强制数据集；存在时记录其哈希
    以便复现。
    """
    commit = run_checked(["git", "rev-parse", "HEAD"], repository)
    dirty_output = run_checked(["git", "status", "--porcelain"], repository)
    working_tree = "CLEAN" if not dirty_output else "DIRTY"

    if release_mode and working_tree != "CLEAN":
        raise RuntimeError(
            "Release experiment requires a CLEAN working tree "
            "(commit or stash your changes first)"
        )

    return {
        "git_commit": commit,
        "working_tree": working_tree,
        "config_sha256": sha256_file(config_path),
        "optimizer_sha256": sha256_file(optimizer_path),
        "dataset_sha256": (
            sha256_file(dataset_path)
            if dataset_path is not None and dataset_path.exists()
            else None
        ),
        "host": platform.node(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
