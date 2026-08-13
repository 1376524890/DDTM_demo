"""一键编排入口：data → train → aruc/valuation → audit → market → contract → feedback → stats → plots → report。

当前为 Phase 0 骨架：加载配置并校验，后续阶段逐步填充各 pipeline 步骤。
每个阶段完成后在此处按顺序接入（见 docs/VERSION_CONTROL_SPEC.md 阶段提交策略）。
"""

from __future__ import annotations

import sys

from . import config as cfg


def main(argv=None) -> int:
    """运行完整实验管线。"""
    config_path = argv[0] if argv and argv[0] else "configs/lab-default.json"
    try:
        conf = cfg.LabConfig.load(config_path)
    except cfg.ConfigError as e:
        print(f"配置加载失败: {e}", file=sys.stderr)
        return 1

    print(f"VALOR-v1 管线启动: experiment_id={conf.experiment_id}")
    print("  [Phase 0] 配置校验通过")

    # TODO(Phase 1): data pipeline → valuation → oracle
    # TODO(Phase 1.5A/1.5B): primitive/action calibration
    # TODO(Phase 2): market + audit-voi + security
    # TODO(Phase 2.5): certification
    # TODO(Phase 3): contract + feedback + welfare
    # TODO(Phase 4): statistics + plotting + report
    print("  [WIP] 后续阶段待接入（Phase 0 骨架）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
