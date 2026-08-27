---
paths:
  - "**/*.py"
  - "**/*.ipynb"
---

# Python conventions in this repository

- **`uv` for everything.** `uv add`, `uv run`, `uv sync`. Never `pip install`, `conda`, `poetry`,
  or `python -m venv` — a `PreToolUse` hook denies those, and the deny message names the `task`
  equivalent. Inside `machine-learning/`, prefer the [Taskfile](machine-learning/Taskfile.yml)
  entry point (`task setup`, `task test`, `task train`) over raw `uv run` where one exists.
- **ruff is the formatter and the linter**, configured in
  [machine-learning/pyproject.toml](machine-learning/pyproject.toml): pydocstyle `D` with the
  google convention, line length 100, `notebooks/` excluded. Docstrings are enforced, not
  suggested. A `PostToolUse` hook runs `ruff check --fix` and `ruff format` on Python files under
  `machine-learning/` after every write.
- **Type hints everywhere.** Untyped public functions do not pass review.
- **Config objects, not scattered lookups.** No `os.getenv` sprinkled through modules; read
  configuration once (Hydra in `machine-learning/`, `pydantic-settings` in services) and pass it.
- **Dependencies declare lower bounds only** so each generated project resolves against current
  releases. The `requires-python = ">=3.11,<3.14"` cap is the one deliberate exception.
- **Placeholders are the product.** In this repository a body that raises `NotImplementedError`
  under a docstring with numbered `TODO` steps is finished work. Do not implement one, remove a
  `TODO`, or "fix" a failing placeholder unless asked to.
