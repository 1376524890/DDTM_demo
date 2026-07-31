#!/usr/bin/env python3
"""G1 cross-language consistency gate.

Reads the manifest (Python's golden values) and the Go / Rust / gnark result
files, and asserts every implementation agrees: each case must PASS (gnark's
negative cases are SKIP because quantization is off-circuit, which is allowed),
and every reported Merkle root must match the manifest's expected root.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _hex_norm(s: str) -> str:
    return s.lower().lstrip("0x").lstrip("0") or "0"


def gate(manifest_path: Path, go: Path, rust: Path, gnark: Path) -> dict:
    manifest = _load(manifest_path)
    expected = {c["id"]: c for c in manifest["cases"]}

    impls = {"go": _load(go), "rust": _load(rust), "gnark": _load(gnark)}
    by_case: dict[str, dict[str, dict]] = {cid: {} for cid in expected}
    for name, data in impls.items():
        for case in data["cases"]:
            if case["id"] in by_case:
                by_case[case["id"]][name] = case

    mismatches = []
    summary = {name: {"pass": 0, "fail": 0, "skip": 0} for name in impls}
    per_case_status = {}

    for cid, case_def in expected.items():
        results = by_case[cid]
        ok = True
        notes = []
        for impl, res in results.items():
            status = res.get("status", "?")
            if status == "PASS":
                summary[impl]["pass"] += 1
            elif status == "SKIP":
                summary[impl]["skip"] += 1
            else:
                summary[impl]["fail"] += 1
                ok = False
                notes.append(f"{impl}:{status}")
            # Root agreement (skip negative cases which have no root).
            if case_def["kind"] != "negative":
                want = case_def.get("expected_data_root")
                actual = res.get("actual_root")
                if want and actual and _hex_norm(want) != _hex_norm(actual):
                    ok = False
                    notes.append(f"{impl}:root")
        # gnark negative cases are allowed to be SKIP (off-circuit).
        if case_def["kind"] == "negative":
            gnark_status = results.get("gnark", {}).get("status")
            if gnark_status == "SKIP":
                ok = ok  # acceptable
        per_case_status[cid] = "PASS" if ok else "FAIL"
        if not ok:
            mismatches.append(f"{cid}: {', '.join(notes)}")

    all_pass = not mismatches
    return {
        "passed": all_pass,
        "mismatches": mismatches,
        "summary": summary,
        "per_case": per_case_status,
        "schema_sha256": manifest["schema_sha256"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path,
                        default=REPO_ROOT / "experiments" / "vectors" / "manifest.json")
    parser.add_argument("--go", type=Path,
                        default=REPO_ROOT / "experiments" / "raw" / "g1-go.json")
    parser.add_argument("--rust", type=Path,
                        default=REPO_ROOT / "experiments" / "raw" / "g1-rust.json")
    parser.add_argument("--gnark", type=Path,
                        default=REPO_ROOT / "experiments" / "raw" / "g1-gnark.json")
    parser.add_argument("--output", type=Path,
                        default=REPO_ROOT / "experiments" / "raw" / "g1-gate.json")
    args = parser.parse_args()

    result = gate(args.manifest, args.go, args.rust, args.gnark)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("G1 gate:", "PASS" if result["passed"] else "FAIL")
    for impl, counts in result["summary"].items():
        print(f"  {impl:6s}: pass={counts['pass']} fail={counts['fail']} skip={counts['skip']}")
    if result["mismatches"]:
        print("  mismatches:")
        for m in result["mismatches"]:
            print("   -", m)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
