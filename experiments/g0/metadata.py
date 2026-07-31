"""Reproducibility metadata: pin every input that affects a release report.

A release run (``--release``) refuses to proceed on a DIRTY tree and records
the SHA-256 of the config, the optimizer source and the dataset, so a report
can be re-derived from a named commit with named inputs.
"""
from __future__ import annotations

import hashlib
import platform
import subprocess
from pathlib import Path
from typing import Any


def run_checked(command: list[str], cwd: Path) -> str:
    """Run a git command and return stripped stdout, raising on failure."""
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    """SHA-256 of a file's raw bytes, streamed in 1 MiB chunks."""
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
    """Collect git + file hashes + host info.

    In ``release_mode`` a DIRTY working tree is a hard error: a formal report
    must be reproducible from a named commit, which requires a clean tree.

    ``dataset_path`` may be ``None`` — G0 is an analytical experiment with no
    mandatory dataset; when present the hash is recorded for reproducibility.
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
