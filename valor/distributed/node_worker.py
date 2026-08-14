"""独立节点进程入口（规范 §17）。

子进程读取环境变量（port/node_id/data_path），加载 committed dataset，构造
NodeExecutor 并启动 FastAPI 服务。由 spawn.py 以独立 OS 进程拉起。
"""

from __future__ import annotations

import os
import pickle
import sys


def _structural_runner(df):
    from valor.quality.native.structural import run_structural

    return run_structural(df).metrics


def _structural_decision(metrics):
    """根据完整率阈值判定（阈值来自任务/校准，不固化）。"""
    threshold = float(os.environ.get("NODE_COMPLETENESS_THRESHOLD", "0.9"))
    for col in metrics:
        if isinstance(metrics[col], dict) and "completeness" in metrics[col]:
            if metrics[col]["completeness"] < threshold:
                return "QUALITY_FAIL"
    return "PASS"


def main() -> int:
    from valor.core.ids import AuditorID
    from valor.distributed.node_server import serve
    from valor.distributed.node_state import AuditorNode
    from valor.distributed.executor import NodeExecutor

    port = int(os.environ["NODE_PORT"])
    node_id = AuditorID(os.environ["NODE_ID"])
    data_path = os.environ["NODE_DATA_PATH"]
    capability = tuple(os.environ.get("NODE_CAPABILITY", "structural").split(","))
    availability = float(os.environ.get("NODE_AVAILABILITY", "1.0"))
    stake = float(os.environ.get("NODE_STAKE", "100.0"))

    with open(data_path, "rb") as f:
        df = pickle.load(f)

    node = AuditorNode(
        node_id=node_id, capability=capability,
        availability=availability, stake=stake,
    )
    executor = NodeExecutor(node, _structural_runner, _structural_decision)
    serve(executor, df, port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
