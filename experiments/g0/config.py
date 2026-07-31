"""把 ``g0-default.json`` 加载并校验为类型化的 ExperimentConfig。"""
from __future__ import annotations

import json
from pathlib import Path

from .models import (
    EconomicPolicy,
    ExperimentConfig,
    InconclusiveAction,
    SprtPolicy,
)


def load_config(path: str | Path) -> ExperimentConfig:
    """读取唯一 JSON 配置并构造一个已校验的 ExperimentConfig。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    config = ExperimentConfig(
        sprt=SprtPolicy(**raw["sprt"]),
        economics=EconomicPolicy(**raw["economics"]),
        inconclusive_action=InconclusiveAction(raw["inconclusive_action"]),
        evaluation_grid=tuple(raw["evaluation_grid"]),
    )
    config.validate()
    return config
