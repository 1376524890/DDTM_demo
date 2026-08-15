"""RunArtifacts —— runs/<run_id>/ 目录落盘（P0 基础设施）。

对齐交接文档第十六节：每笔正式交易形成 runs/<run_id>/ 目录，含
    manifest.json
    00_environment/ 01_dataset/ 02_listing/ ... 13_feedback/
    transaction_trace.jsonl  formula_trace.jsonl  money_ledger.jsonl  state_trace.jsonl
    report.json  report.md

提供统一写入 API，保证每次 run 的 artifact 结构稳定、可被 FullChainGate 检查。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from valor.core.ids import validate_id


class RunArtifacts:
    """管理一次 run 的 artifact 目录。"""

    def __init__(self, run_dir: str | Path, *, run_id: str, create: bool = True) -> None:
        self.run_id = run_id
        validate_id(run_id, name="run_id")
        self.root = Path(run_dir)
        if create:
            self.root.mkdir(parents=True, exist_ok=True)

    # ---- 子目录 ----
    def sub(self, name: str) -> Path:
        d = self.root / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ---- 通用写 JSON ----
    def write_json(self, rel: str | Path, obj: Any) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(obj, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )
        return p

    def write_jsonl(self, rel: str | Path, rows: list[dict[str, Any]]) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False, default=_json_default) for r in rows),
            encoding="utf-8",
        )
        return p

    def write_text(self, rel: str | Path, text: str) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    # ---- 常用命名 ----
    def write_manifest(self, manifest_plain: dict[str, Any]) -> Path:
        return self.write_json("manifest.json", manifest_plain)

    def write_trace(self, ledger_rows: list[dict[str, Any]]) -> Path:
        return self.write_jsonl("transaction_trace.jsonl", ledger_rows)

    def write_formula_trace(self, formula_rows: list[dict[str, Any]]) -> Path:
        return self.write_jsonl("formula_trace.jsonl", formula_rows)

    def write_money_ledger(self, rows: list[dict[str, Any]]) -> Path:
        return self.write_jsonl("money_ledger.jsonl", rows)

    def write_state_trace(self, rows: list[dict[str, Any]]) -> Path:
        return self.write_jsonl("state_trace.jsonl", rows)

    def write_report(self, report_json: dict[str, Any], report_md: str) -> None:
        self.write_json("report.json", report_json)
        self.write_text("report.md", report_md)


def _json_default(o: Any) -> Any:
    """兜底序列化（numpy 标量等）。"""
    import numpy as np

    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if hasattr(o, "to_plain"):
        return o.to_plain()
    raise TypeError(f"无法序列化类型: {type(o).__name__}")


__all__ = ["RunArtifacts"]
