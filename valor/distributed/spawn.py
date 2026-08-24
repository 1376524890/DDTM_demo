"""独立节点进程拉起器（规范 §17，进程管理器方案）。

把 committed dataset 序列化到临时文件，用 subprocess 以独立 OS 进程启动
N 个 auditor 节点服务（FastAPI + uvicorn），并等待就绪。
"""

from __future__ import annotations

import os
import pickle
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pandas as pd


def spawn_nodes(
    *,
    committed_data: pd.DataFrame,
    node_ids: list[str],
    ports: list[int],
    env_overrides: dict | None = None,
) -> tuple[list[subprocess.Popen], str]:
    """启动多个独立节点进程，返回 (processes, data_path)。

    data_path 指向序列化的 committed dataset（共享只读对象存储）。
    """
    if len(node_ids) != len(ports):
        raise ValueError("node_ids 与 ports 数量必须一致")
    tmpdir = tempfile.mkdtemp(prefix="valor-nodes-")
    data_path = os.path.join(tmpdir, "committed.pkl")
    with open(data_path, "wb") as f:
        pickle.dump(committed_data, f)

    procs: list[subprocess.Popen] = []
    base_env = dict(os.environ)
    base_env.setdefault("PYTHONPATH", str(Path(__file__).resolve().parent.parent.parent))
    for nid, port in zip(node_ids, ports):
        env = dict(base_env)
        env.update({
            "NODE_ID": nid,
            "NODE_PORT": str(port),
            "NODE_DATA_PATH": data_path,
        })
        if env_overrides:
            env.update(env_overrides)
        proc = subprocess.Popen(
            [sys.executable, "-m", "valor.distributed.node_worker"],
            env=env, cwd=str(Path(__file__).resolve().parent.parent.parent),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        procs.append(proc)
    _wait_healthy(ports, timeout=30.0)
    return procs, data_path


def _wait_healthy(ports: list[int], timeout: float = 30.0) -> None:
    """等待所有节点 /health 就绪。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        ready = 0
        for port in ports:
            try:
                r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0, trust_env=False)
                if r.status_code == 200:
                    ready += 1
            except Exception:
                pass
        if ready == len(ports):
            return
        time.sleep(0.3)
    raise TimeoutError(f"节点未在 {timeout}s 内就绪: {len(ports)} 个，就绪 {ready}")


def teardown(procs: list[subprocess.Popen]) -> None:
    """终止并回收节点进程。"""
    for p in procs:
        p.terminate()
    for p in procs:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
