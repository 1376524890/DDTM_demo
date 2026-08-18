# Repository Guidelines

VALOR is a Python prototype for rights-aware, quality-verifiable, usage-auditable data transactions. The frozen specification `VALOR_可实施原型系统_完整数学代码闭环与开发规范.md` is the normative design source; code and docs must stay aligned with it.

## Project Structure & Module Organization

- `valor/` — Python package: mechanism implementation, CLI, engine, adapters, quality, pricing, security, privacy audit, and experiments.
- `tests/` — test suite organized by domain: `unit/`, `property/`, `engine/`, `privacy_audit/`, `security/`, `system/`, etc.
- `configs/` — JSON run configurations and JSON Schemas. Business parameters must be explicit; no hidden defaults.
- `scripts/` — reproduction and audit scripts.
- `docs/` — design, archive, and version-control specifications.
- `raw/`, `runs/`, `reports/figures/` — regenerable outputs, gitignored.
- `data/raw/`, `data/prepared/` — large datasets, gitignored.

## Build, Test, and Development Commands

```bash
python -m pip install -e ".[dev]"                # install package and dev deps
python -m pytest -q                              # run the full test suite
python -m valor transaction run --config configs/experiments/full_transaction.json
python -m valor experiment run --config configs/experiments/sweep.json
python -m valor calibration run --config <calibration.json>
python -m valor gate phase0 --config tests/fixtures/phase0_valid.json
python scripts/check_business_defaults.py --root valor
python scripts/reverse_self_audit.py
```

Business CLI commands require `--config` or `--run-dir`.

## Coding Style & Naming Conventions

- Python: `snake_case` modules/functions/variables, `CamelCase` classes, `UPPER_SNAKE_CASE` constants.
- Modules and directories use `snake_case`; config files use `kebab-case` or `snake_case` matching their JSON Schema.
- Keep core formula inputs explicit and traceable to config or upstream artifacts; never fall back to silent business defaults.
- Prefer deterministic, canonical serialization for hashes, logs, and result JSON.

## Testing Guidelines

- Tests live in `tests/`, use `test_*.py`, and name functions `test_*`.
- Before merging, run `python -m pytest -q` and the default-value/forbidden-pattern scanners.
- Cover fail-closed paths: missing config, invalid rights, and breach evidence.

## Commit & Pull Request Guidelines

Follow Conventional Commits with Chinese subjects:

```text
feat(core): 新增 canonical JSON 与哈希链基础工具
fix(engine): 修复 P4 quorum-by-result 计数
test(params): 空业务配置 fail-closed 单测
docs: 建立目录归档与版本控制规范
```

Scopes follow module names (`core`, `engine`, `gate`, `audit`, `privacy-audit`, `experiments`, `docs`, etc.). Do not use `--no-verify`; run tests before committing. PRs should describe the change, reference the phase/issue, include gate evidence, and update archive/version-control specs when structure rules change.

## Security & Configuration Tips

- Keep secrets, local configs, and private data out of the repo (`configs/local/`, `.env`, `seller_private/`).
- Configuration must be fail-closed: reject unknown fields and missing required parameters.
- Audit and settlement must derive from evidence and upstream artifacts, not scenario flags.
