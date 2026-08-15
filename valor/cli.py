"""VALOR CLI 契约（规范 §71）。

除 --help / --version 外，需要业务参数的 CLI 不接受省略 --config。

    python -m valor quality reproduce --config <path>
    python -m valor quality certify   --config <path>
    python -m valor node serve        --config <path>
    python -m valor audit run         --config <path>
    python -m valor valuation run     --config <path>
    python -m valor transaction run   --config <path>
    python -m valor experiment run    --config <path>
    python -m valor report build      --run-dir <path>

# Phase 0-8 已全部实现；业务命令均要求 --config/--run-dir。
对应 Phase 完成前打印"待实现"并返回非零，但同样强制 --config/--run-dir。
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__


def cmd_version() -> int:
    print(f"VALOR {__version__}")
    return 0


def _add_cmd(sub, name: str, help_: str) -> argparse.ArgumentParser:
    """添加一个业务命令子解析器（要求 --config，缺失由 argparse 强制）。"""
    p = sub.add_parser(name, help=help_)
    p.add_argument("--config", required=True)
    return p


def cmd_transaction_run(config_path: str) -> int:
    """全流程交易（Phase 8）：主链 Entitlement→…→结算/反馈，输出全部数值。"""
    import json
    import os

    from .run import run_full_transaction

    cfg = json.loads(open(config_path, encoding="utf-8").read())
    result = run_full_transaction(cfg)
    os.makedirs("raw", exist_ok=True)
    with open("raw/run_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    # 逐步公式/输入/输出记录（主链机制运行档案）
    with open("raw/transaction_trace.json", "w", encoding="utf-8") as f:
        json.dump({"steps": result.get("trace", [])},
                  f, ensure_ascii=False, indent=2)
    # 生成报告与价格边界图
    from .report import build_report
    from .plotting import plot_price_bounds

    build_report("raw/run_result.json", "reports/full_transaction.md")
    pr = result.get("pricing", {})
    if pr.get("p_max") is not None and pr.get("p_min") is not None:
        plot_price_bounds(pr["p_max"], pr["p_min"], result.get("decision", ""),
                          "reports/figures/price_bounds.png")
    print(f"成交决策: {result.get('decision')}")
    return 0


def _cmd_engine(args: argparse.Namespace) -> int:
    """engine 收敛层命令：capstone / calibrate / acceptance。"""
    import json
    from pathlib import Path

    from .engine import CapstoneScenario

    if args.cmd == "capstone":
        sc = CapstoneScenario(**json.loads(Path(args.scenario).read_text(encoding="utf-8")))
        from .engine import run_capstone

        calibration = None
        if args.calibration_dir:
            from .engine.calibration import CalibrationBundle, FrozenArtifact

            bundle_json = json.loads(
                Path(args.calibration_dir).read_text(encoding="utf-8"))
            calibration = CalibrationBundle(
                valuation=(
                    FrozenArtifact("valuation_calibration",
                                   bundle_json["valuation"]["data"])
                    if bundle_json.get("valuation") else None),
                likelihood=(
                    FrozenArtifact("audit_likelihood",
                                   bundle_json["likelihood"]["data"])
                    if bundle_json.get("likelihood") else None),
                certificate=(
                    FrozenArtifact("audit_policy_certificate",
                                   bundle_json["certificate"]["data"])
                    if bundle_json.get("certificate") else None),
            )
        res = run_capstone(sc, run_dir=args.run_dir, calibration=calibration)
        print(json.dumps(res.to_plain(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "calibrate":
        from valor.data.download import load_dataset
        from .engine.calibration_runner import CalibrationConfig, run_offline_calibration

        handle = load_dataset(args.dataset)
        from valor.core.hashing import content_hash

        pool = handle.X.iloc[:min(500, len(handle.X))]
        cfg = CalibrationConfig(
            historical_pool=pool,
            dataset_hash=content_hash({"dataset": args.dataset, "n": len(pool)}),
            trainer_hash=content_hash({"trainer": "MLP"}),
            seed=0,
        )
        bundle = run_offline_calibration(cfg, run_dir=args.out_dir)
        print(json.dumps(bundle.to_plain(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "acceptance":
        from .engine.acceptance import run_acceptance

        results = run_acceptance(run_dir=args.run_dir)
        for r in results:
            print(f"{r.scenario_id}: {r.terminal} "
                  f"({'PASS' if r.passed else 'FAIL'})")
        return 0 if all(r.passed for r in results) else 1

    print(f"未知 engine 命令: {args.cmd}", file=sys.stderr)
    return 2


def _not_implemented(args: argparse.Namespace) -> int:
    """业务命令在后续 Phase 才实现；此处打印并返回非零。"""
    phase = args.phase
    cmd = args.cmd
    print(
        f"命令 '{cmd}' 属于 Phase {phase}，当前 Phase 0 尚未实现",
        file=sys.stderr,
    )
    return 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="valor", description="VALOR 数据交易原型系统 CLI"
    )
    parser.add_argument("--version", action="store_true", help="输出版本")
    # 子命令非 required，以便 --help / --version 无需子命令即可运行（规范 §71）
    sub = parser.add_subparsers(dest="command")

    # ---- quality（Phase 1）----
    q = sub.add_parser("quality", help="质量复现/认证")
    qsub = q.add_subparsers(dest="cmd", required=True)
    qsub.add_parser("reproduce", help="质量复现（Gate B）").add_argument(
        "--config", required=True
    )
    qsub.add_parser("certify", help="质量认证").add_argument(
        "--config", required=True
    )

    # ---- node（Phase 2）----
    n = sub.add_parser("node", help="分布式节点服务")
    nsub = n.add_subparsers(dest="cmd", required=True)
    nsub.add_parser("serve", help="启动 auditor 节点").add_argument(
        "--config", required=True
    )

    # ---- audit（Phase 3）----
    a = sub.add_parser("audit", help="审计运行")
    asub = a.add_subparsers(dest="cmd", required=True)
    asub.add_parser("run", help="Audit-VOI 运行").add_argument(
        "--config", required=True
    )

    # ---- valuation（Phase 4）----
    v = sub.add_parser("valuation", help="估值运行")
    vsub = v.add_subparsers(dest="cmd", required=True)
    vsub.add_parser("run", help="Data-VOI 运行").add_argument(
        "--config", required=True
    )

    # ---- transaction（Phase 0）----
    t = sub.add_parser("transaction", help="交易运行")
    tsub = t.add_subparsers(dest="cmd", required=True)
    tsub.add_parser("run", help="交易硬门槛").add_argument(
        "--config", required=True
    )

    # ---- experiment（Phase 8）----
    e = sub.add_parser("experiment", help="实验运行")
    esub = e.add_subparsers(dest="cmd", required=True)
    esub.add_parser("run", help="RQ 实验运行").add_argument(
        "--config", required=True
    )

    # ---- report（Phase 8）----
    r = sub.add_parser("report", help="报告构建")
    rsub = r.add_subparsers(dest="cmd", required=True)
    rsub.add_parser("build", help="构建报告").add_argument(
        "--run-dir", required=True
    )

    # ---- gate（Phase 门禁，检查单 T）----
    gg = sub.add_parser("gate", help="Phase Gate 检查")
    ggsub = gg.add_subparsers(dest="cmd", required=True)
    ggsub.add_parser("phase0", help="Phase 0 验收 Gate").add_argument(
        "--config", required=True
    )

    # ---- engine（P0-P13 收敛层）----
    en = sub.add_parser("engine", help="收敛层（capstone/calibration/acceptance）")
    ensub = en.add_subparsers(dest="cmd", required=True)
    cap = ensub.add_parser("capstone", help="运行 MNIST capstone 交易")
    cap.add_argument("--scenario", required=True)
    cap.add_argument("--run-dir", default="runs")
    cap.add_argument("--calibration-dir", default=None)
    cal = ensub.add_parser("calibrate", help="离线校准（likelihood+certification+valuation）")
    cal.add_argument("--dataset", default="breast_cancer")
    cal.add_argument("--out-dir", default="calibration")
    acc = ensub.add_parser("acceptance", help="五场景验收 C0-C4")
    acc.add_argument("--run-dir", default="runs/acceptance")

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        return cmd_version()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "transaction" and args.cmd == "run":
        return cmd_transaction_run(args.config)

    # engine 收敛层（P0-P13）
    if args.command == "engine":
        return _cmd_engine(args)

    # quality reproduce（Phase 1）：Reference Reproduction Gate
    if args.command == "quality" and args.cmd == "reproduce":
        from .quality.reproduce_cli import run_quality_reproduce

        return run_quality_reproduce(args.config)

    # report build（Phase 8）
    if args.command == "report" and args.cmd == "build":
        from .report import build_report

        run_dir = args.run_dir
        return build_report(
            os.path.join(run_dir, "run_result.json"),
            os.path.join(run_dir, "report.md"),
        )

    # experiment run（Phase 8）
    if args.command == "experiment" and args.cmd == "run":
        from .experiment import run_experiments

        return run_experiments(args.config)

    # gate phase0：输出机器可读 JSON（检查单 T）
    if args.command == "gate" and args.cmd == "phase0":
        import json as _json

        from .gate import run_phase0_gate

        result = run_phase0_gate(args.config)
        print(_json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "PASS" else 1

    # 其余业务命令：Phase 尚未实现，但 --config/--run-dir 已由 argparse 强制
    phase_map = {
        ("quality", "reproduce"): 1,
        ("quality", "certify"): 1,
        ("node", "serve"): 2,
        ("audit", "run"): 3,
        ("valuation", "run"): 4,
        ("experiment", "run"): 8,
        ("report", "build"): 8,
    }
    args.phase = phase_map.get((args.command, args.cmd), "?")
    return _not_implemented(args)


if __name__ == "__main__":
    sys.exit(main())
