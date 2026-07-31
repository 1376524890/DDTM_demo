"""Load and validate ``g0-default.json`` into a typed ExperimentConfig."""
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
    """Read the single JSON config and build a validated ExperimentConfig."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    config = ExperimentConfig(
        sprt=SprtPolicy(**raw["sprt"]),
        economics=EconomicPolicy(**raw["economics"]),
        inconclusive_action=InconclusiveAction(raw["inconclusive_action"]),
        evaluation_grid=tuple(raw["evaluation_grid"]),
    )
    config.validate()
    return config
