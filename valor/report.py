"""VALOR CLI 入口：报告生成 + 配置校验 + 版本查询。

Phase 0 gate：
- `python -m valor.report --version` 可运行，输出包版本。
- `python -m valor.report --check-config <config>` 校验配置（缺失参数报错）。
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from . import config as cfg
from .metadata import build_repro_metadata


def cmd_version() -> int:
    """输出包版本（Phase 0 gate）。"""
    print(f"VALOR-v1 {__version__}")
    return 0


def cmd_check_config(config_path: str) -> int:
    """校验配置文件：加载完整配置，缺失参数即报 ConfigError。"""
    try:
        conf = cfg.LabConfig.load(config_path)
    except cfg.ConfigError as e:
        print(f"配置校验失败: {e}", file=sys.stderr)
        return 1
    print(f"配置校验通过: experiment_id={conf.experiment_id}, seed={conf.seed}")
    print(f"  data.n_candidates={conf.data.n_candidates}")
    print(f"  economics.currency={conf.economics.currency}")
    print(f"  payoff.matrix={conf.economics.payoff.to_plain()['matrix']}")
    return 0


def cmd_run(config_path: str) -> int:
    """运行完整实验管线（Phase 4 后完整实现；当前仅校验并输出元数据骨架）。"""
    try:
        conf = cfg.LabConfig.load(config_path)
    except cfg.ConfigError as e:
        print(f"配置加载失败: {e}", file=sys.stderr)
        return 1

    # 组装 config 的 JSON 原生表示，用于 repro 元数据
    config_plain = {
        "experiment_id": conf.experiment_id,
        "seed": conf.seed,
        "data": {
            "dataset_name": conf.data.dataset_name,
            "n_candidates": conf.data.n_candidates,
            "split_seed": conf.data.split_seed,
        },
        "economics": {
            "currency": conf.economics.currency,
            "payoff": conf.economics.payoff.to_plain(),
        },
    }
    repro = build_repro_metadata(config_plain)
    print(json.dumps({"status": "phase0-skeleton", "repro": repro}, ensure_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="VALOR-v1 CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="输出包版本")
    p_check = sub.add_parser("check-config", help="校验配置文件")
    p_check.add_argument("config_path")
    p_run = sub.add_parser("run", help="运行实验管线")
    p_run.add_argument("--config", default="configs/lab-default.json")

    args = parser.parse_args(argv)
    if args.command == "version":
        return cmd_version()
    if args.command == "check-config":
        return cmd_check_config(args.config_path)
    if args.command == "run":
        return cmd_run(args.config)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
