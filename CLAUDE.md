# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A collection of project starters, one directory each: `machine-learning/`,
`docs/`, and three planned but empty (`backend/`, `frontend/`, `data-engineering/`).

**Every template here is a documented placeholder, and that is the deliverable.**
Function bodies raise `NotImplementedError`, docstrings carry numbered `TODO`
steps, and documents have sections with the content left blank. Do not implement
a placeholder, remove a `TODO`, or "finish" a blank section unless asked to.

This changes what a failure means. A fresh run of `machine-learning/` gets as far
as the setup cell and stops on `NotImplementedError` — that is the expected
result, not a bug: it proves the environment, the imports and the config
directory all resolved, and only the logic is missing.

## Working agreement

These four rules outrank convenience. They apply to every task here, including
ones described as quick or trivial.

### Never guess

If a fact is not in the repository, in the prompt, or in tool output you have
actually read, you do not know it — ask.

- Do not infer a version, a path, a framework, an API shape, or the user's intent
  from a name or a convention seen elsewhere. Read the file, or ask.
- Do not invent commands, flags, or config keys. Every command you state must
  exist in [machine-learning/Taskfile.yml](machine-learning/Taskfile.yml) or in a
  README here.
- Placeholder text is a question to ask, not a blank to fill from imagination.
  In this repository especially, a `TODO` is the product.

When the unknown does not block the work: do everything that does not depend on
it, state the assumption explicitly, and continue. When proceeding under a wrong
assumption would be unsafe, destructive, or would waste the work entirely — stop
and ask first.

### Ask before "fixing" code the user supplied

When the user provides a script, a diff, or a file that does not meet the
conventions below, do not silently rewrite it.

1. Name the specific rule it misses and the line it misses it on.
2. Ask one question per genuine ambiguity — not a questionnaire. If the deviation
   is unambiguous and mechanical, fix it and report it rather than asking.
3. Wait for the answer before restructuring, renaming, reformatting, or changing
   dependencies. Deviations are often deliberate.

Improvements you noticed but were not asked for are reported, not applied.

### Always report what was done and changed

Every response that touched anything ends with a plain, factual account:

- **Files changed** — each path, and what changed in it, in one line each.
- **Verified** — the command actually run and its actual result. Not "tests
  should pass"; either the output, or an explicit "not run".
- **Not done** — anything skipped, blocked, or left out, and why.

Report failures as failures. Never describe work as complete on the strength of
having written the code.

### Hold the scope

Deliver exactly the requested scope. If part of it is blocked, finish every other
part in full and say precisely what was left out and why.

## Commands

Everything below runs from `machine-learning/`. It uses [Task](https://taskfile.dev)
as the entry point and [uv](https://docs.astral.sh/uv/) underneath; `task` with no
argument lists every available task.

| Command | |
|---|---|
| `task setup` | full environment (`uv sync --all-extras`) plus git hooks |
| `task sync` | lighter environment: base + dev + notebooks + viz |
| `task lint` | `ruff check` and `ruff format --check` |
| `task format` | auto-fix and format |
| `task test` | pytest |
| `task test -- tests/test_split.py::test_name` | one test — everything after `--` is forwarded |
| `task check` | lint then test |
| `task lab` | JupyterLab |
| `task clean:data` | the cleaning + split stage as a script |
| `task train -- models=model_a seed=7` | train one model, with Hydra overrides |
| `task sweep -- models=model_a,model_b` | Hydra multirun |
| `task api` / `task demo` | FastAPI service / Streamlit demo |
| `task dvc:repro` / `task dvc:dag` | reproduce the pipeline / show the stage graph |
| `task mlflow` | MLflow UI on the local `./mlruns` store |

`uv run pre-commit run --all-files` runs the hooks over the whole tree.

The `docs/` templates have no build step — they are Markdown, copied into other
projects.

## Architecture

The parts worth knowing cost several files to reconstruct, so they are stated
once here. Each is expanded in [machine-learning/README.md](machine-learning/README.md).

**The leakage boundary — notebook 01 vs 02x.** Notebook `01_clean_and_split` does
only deterministic, model-agnostic work: schema validation, deduplication,
dropping non-predictive columns and invalid labels, filtering on hard external
bounds, and the train/test split. Anything that *learns* from the data —
imputation, statistical outlier removal, scaling, encoding, feature engineering —
belongs in a `02x` notebook, fitted on the training split only. The test is where
the threshold comes from: a bound known before seeing the data belongs in 01; a
threshold derived from the data belongs in 02x. The test split is frozen from the
end of 01 until notebook 03.

**Single sources of truth.** `src/data/split.py` and `src/evaluation/metrics.py`
are authoritative — every notebook and script uses them. Models validated on
different folds, or scored with differently defined metrics, cannot be compared,
and the comparison is the point.

**Dependency direction.** `app/` imports from `src/`, never the reverse. The
preprocessor and the model are serialized together, so evaluation and serving can
only `transform`, never `fit`.

**Configuration.** Hydra composes `configs/config.yaml` from `configs/data.yaml`
plus exactly one `configs/models/*.yaml`. Split configuration, `val_size`
included, lives in `configs/data.yaml` and nowhere else. Model configs keep
`model:` (constructor arguments), `optim:` and `train:` in separate groups because
`instantiate()` passes `model:` straight to `__init__`. In notebooks the
`@hydra.main` decorator does not work — use the Compose API through
`src.config.load_config()`.

**Three versioning layers.** DVC versions file contents; Git plus the Hydra YAML
versions the rules that produced them; MLflow versions the runs. The Git commit
ties them together. DVC is deliberately not initialised in the template.

**The test suite is a progress board.** Each test skips with the module it is
waiting on, so `task test` reports how far the implementation has got. Fixtures
in [machine-learning/tests/conftest.py](machine-learning/tests/conftest.py) are
tiny and synthetic on purpose: tests must never depend on the DVC-tracked dataset.

## Conventions that are easy to get wrong

- **Docstrings are linted.** ruff runs with `D` (pydocstyle, google convention)
  enabled, line length 100, `notebooks/` and `*.md` excluded — see
  [machine-learning/pyproject.toml](machine-learning/pyproject.toml). The
  documentation standard the placeholders follow is enforced, not suggested.
  `src/**` ignores `ARG001`/`ARG002` because unused arguments are the point in a
  placeholder body.
- **Taskfile commands stay cross-platform.** Task runs them through its own POSIX
  shell, so no platform binaries (`rm`, `find`) — shell out to
  `uv run python -c ...` instead, as `task clean` does.
- **Dependencies declare lower bounds only**, so each generated project resolves
  against current releases. The `requires-python = ">=3.11,<3.14"` cap is the one
  deliberate exception: `hydra-core` 1.3.x cannot build its argument parser on
  3.14, which breaks every `@hydra.main` entry point. The template intentionally
  ships without `uv.lock`; generated projects commit theirs.
- **`docs/*.template.md` keep the `.template.md` suffix in this repository.**
  GitHub auto-discovers `SECURITY.md` and `CONTRIBUTING.md` in the root, in
  `.github/`, and in `docs/` — without the suffix this repository would publish a
  blank template as its own security policy. The suffix is dropped on copy.
- **Relative links inside `docs/` templates are written for the destination
  project root**, not for this repository. `SECURITY.md`, `docs/adr/`,
  `.github/CODEOWNERS` resolve once copied; they are not broken links to fix here.
- **Two template conventions**, documented in [README.md](README.md):
  screaming-snake-case placeholders in angle brackets, verifiable with
  `grep -n '<[A-Z][A-Z0-9_]*>' FILE`, and HTML-comment markers —
  `REQUIRED-IF`, `OPTIONAL`, `GUIDANCE` — that are resolved and deleted along
  with the sections they govern. A section with no marker is required, so a
  reviewer can tell a deliberate omission from an oversight. New templates follow
  both and close with a checklist that tells the user to delete it.

## Claude Code configuration

`.claude/` holds three layers, in increasing order of how hard they bind.

**Skills** (`.claude/skills/`) — eight, each a router `SKILL.md` plus a `references/`
directory. Read the router first: it carries the routing table and the cross-cutting
rules, then points at the one or two reference files the task needs. Two cover the ML
ground: [`ai-engineering`](.claude/skills/ai-engineering/SKILL.md) for anything built
on top of an LLM (prompts, RAG, agents, evals, fine-tuning, serving) and
[`machine-learning`](.claude/skills/machine-learning/SKILL.md) for classical ML and
PyTorch (EDA and splitting, architecture, training, interpretability, deployment,
experiments, statistics). Fine-tuning an open-weight model is `ai-engineering`;
training from scratch is `machine-learning`. The other six are per-stack lifecycles
plus `coding-mentor-mode`.

**Rules** (`.claude/rules/`) — six topic files, context rather than enforcement. Only
`ai-ml-routing.md` loads every session; the rest carry `paths:` frontmatter and load
only when a matching file is touched.

**Hooks** (`.claude/hooks/`, wired in `.claude/settings.json`) — four stdlib-only
Python scripts, all failing open on bad input or a missing tool.

| Hook | Event | Effect |
|---|---|---|
| `skill_router.py` | UserPromptSubmit | Advisory: names the router and reference file a prompt matches. |
| `ml_lint.py` | PostToolUse Write/Edit | Advisory: `ruff check --fix` + `format` on Python under `machine-learning/`; silent without `.venv`. |
| `write_guard.py` | PreToolUse Write/Edit | **Denies** writes breaking `SKILL.md`/rule frontmatter, or overwriting a frozen test split. |
| `bash_guard.py` | PreToolUse Bash | **Denies** pip/conda/poetry/venv, and staging checkpoints, `mlruns/` or large data into git. |

A deny is not a malfunction — its reason names the rule and the alternative. Editing
any of this is governed by
[`.claude/rules/skill-authoring.md`](.claude/rules/skill-authoring.md).

## Before calling work done

1. If Python changed: `task check` has been **run** from `machine-learning/`, not
   assumed.
2. If a `docs/` template changed: `grep -n '<[A-Z][A-Z0-9_]*>'` on it still
   returns its placeholders, and no `GUIDANCE` comment was left describing
   something that is no longer there.
3. If anything under `.claude/` changed: the affected hook scripts have been **run**
   against sample stdin (each script's docstring carries an invocation), both the
   trigger and the fail-open path confirmed, and the skill listing checked with
   `/context` after a restart — hooks and skills are read at session start.
4. The report from "Always report what was done and changed" is written, with the
   real command output and every skipped item named.
