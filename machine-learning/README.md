# Machine Learning Project Template

A leakage-safe starting point for a machine learning project: shared splitting
and metrics, Hydra configuration, DVC + MLflow versioning, and a serving layer —
wired together, with the implementations left to you.

Every module here is a **documented placeholder**. Signatures, contracts,
docstrings and numbered `TODO` steps are in place; the bodies raise
`NotImplementedError`. The structure and the rules are the deliverable — fill in
the logic for the project at hand.

The full rationale behind every convention is in [PROJECT.md](PROJECT.md). This
file covers how to *use* the template.

---

## Quickstart

```bash
task setup
```

Then work through the notebooks in order:

| Notebook | What it does | Colab |
|---|---|---|
| [`00_eda.ipynb`](notebooks/00_eda.ipynb) | Understand the data. Produces insights, not artifacts. | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/NguyenVu04/templates/blob/main/machine-learning/notebooks/00_eda.ipynb) |
| [`01_clean_and_split.ipynb`](notebooks/01_clean_and_split.ipynb) | Deterministic cleaning and the train/test split. | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/NguyenVu04/templates/blob/main/machine-learning/notebooks/01_clean_and_split.ipynb) |
| [`02a_model_a.ipynb`](notebooks/02a_model_a.ipynb) | One notebook per model: preprocessing, tuning, training. | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/NguyenVu04/templates/blob/main/machine-learning/notebooks/02a_model_a.ipynb) |
| [`03_evaluation.ipynb`](notebooks/03_evaluation.ipynb) | Final comparison on the held-out test set. | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/NguyenVu04/templates/blob/main/machine-learning/notebooks/03_evaluation.ipynb) |

Each notebook is a sectioned template: every section states what belongs in it,
what does not, and which `src/` function to call.

## Running in Google Colab

Click a badge above. Every notebook opens with a **section 0** that bootstraps
its own environment — run it first and the rest of the notebook behaves as it
does locally:

- It clones this repository into `/content` and puts the project root on
  `sys.path`, so `from src.config import load_config` works without an editable
  install.
- It installs only what Colab does not already ship — `hydra-core`, plus
  `mlflow` in `02a`. numpy, pandas, pyarrow, scikit-learn, joblib, matplotlib
  and seaborn are preinstalled there, so nothing is upgraded and Colab never
  asks for a runtime restart.
- It `chdir`s to the project root, so the root-relative paths in
  `configs/data.yaml` resolve exactly as they do for `task clean:data`.

The same cell runs locally, where it does nothing but find the project root —
which also fixes JupyterLab starting its kernel in `notebooks/`.

**Data and artifacts.** `data/` and `models/` are DVC-tracked and are not part
of a Git clone, so a fresh Colab runtime has neither. Section 0 ships a
commented-out cell that mounts Google Drive and repoints the config at it via
`CONFIG_OVERRIDES`; uncomment it and set the Drive path. Drive is also what
makes notebook 01's splits and notebook 02a's artifact survive a runtime reset —
`/content` does not.

**What a Colab run proves today.** Every `src/` body is a placeholder raising
`NotImplementedError`, so a fresh clone gets as far as the setup cell and stops
there. That failure *is* the expected result: it means the environment, the
imports and the config directory all resolved, and only the logic is missing.

## Adapting the template to a new project

1. **Rename the project.** `pyproject.toml` (`name`), and `<project-name>` in
   `configs/config.yaml` and `app/api/main.py`. If you forked or moved the
   repository, repoint Colab too: the badge URL at the top of each notebook and
   the `REPO_URL` / `BRANCH` / `SUBDIR` values in its section 0 bootstrap cell.
2. **Describe the data.** Fill in `configs/data.yaml`: paths, target, grouping
   column, split scheme, and one `schema.columns` entry per column. Every hard
   bound needs a `source` — the standard, specification or physical limit it
   comes from.
3. **Implement `src/` bottom-up.** The placeholders are ordered by dependency:

   | Order | Module | Unblocks |
   |---|---|---|
   | 1 | `src/config.py`, `src/utils/seed.py` | every notebook's setup cell |
   | 2 | `src/data/load.py`, `src/data/schema.py` | notebooks 00 and 01 |
   | 3 | `src/data/split.py` | notebook 01 and every model |
   | 4 | `src/data/clean.py` | notebook 01 and the DVC pipeline |
   | 5 | `src/evaluation/metrics.py`, `src/utils/io.py` | training and evaluation |
   | 6 | `src/models/model_a.py` | notebook 02a |
   | 7 | `src/utils/tracking.py`, `src/evaluation/analysis.py` | reporting |
   | 8 | `app/` | serving |

   The test suite mirrors this order — each test is skipped with the module it
   is waiting for, so `task test` doubles as a progress board.
4. **Rename `model_a`** to your first real model: the module in `src/models/`,
   the class, `configs/models/model_a.yaml`, and `notebooks/02a_model_a.ipynb`.
   Add further models by copying all four.
5. **Delete what you do not need.** DVC, MLflow and `app/` are independent —
   remove the extra, the config block and the directory together.

## Project layout

```
machine-learning/
├── data/            raw · interim · processed · external   (DVC-tracked)
├── notebooks/       00 EDA · 01 clean+split · 02x models · 03 evaluation
├── src/
│   ├── data/        load · clean · schema · split ★
│   ├── models/      base · one module per model · train
│   ├── evaluation/  metrics ★ · analysis
│   └── utils/       seed · io · tracking
├── configs/         config.yaml · data.yaml · models/*.yaml
├── app/             api (FastAPI) · demo (Streamlit) · Dockerfile
├── models/          serialized artifacts                   (DVC-tracked)
├── reports/         figures · results
├── tests/
├── dvc.yaml         pipeline definition
├── Taskfile.yml     frequently used commands
└── pyproject.toml
```

★ Shared and authoritative: every notebook and script must use these.

## The rules that matter

**Notebook 01 vs 02x — the leakage boundary.** Notebook 01 does only
deterministic, model-agnostic work: schema validation, deduplication, dropping
non-predictive columns and invalid labels, filtering on hard external bounds,
and the train/test split. Everything that *learns* from data — imputation,
statistical outlier removal, scaling, encoding, feature engineering — happens in
a `02x` notebook, fitted on the training split only.

The distinction is where the threshold comes from:

| Type | Criterion | Where |
|---|---|---|
| Invalid record | Violates a bound known *before* seeing the data | 01 |
| Statistical outlier | Threshold derived *from* the data | 02x |

**One splitter, one metric module.** `src/data/split.py` and
`src/evaluation/metrics.py` are used by everything. Models validated on
different folds, or scored with differently defined metrics, cannot be compared —
and the comparison is the point.

**The test split is frozen** from the end of notebook 01 until notebook 03.

**Preprocessor and model are saved together**, so evaluation and serving can
only `transform`, never `fit`.

**`app/` imports from `src/`, never the reverse.**

## Configuration

Hydra composes `configs/config.yaml` from the data config plus exactly one model
config. Override anything from the command line:

```bash
task train -- models=model_a seed=7 models.optim.lr=1e-3
```

In notebooks the `@hydra.main` decorator does not work — use the Compose API
through `src.config.load_config()`.

Split configuration, including `val_size`, lives in `configs/data.yaml` and
nowhere else. Model configs keep `model:` (constructor arguments), `optim:` and
`train:` in separate groups, because `instantiate()` passes `model:` straight to
`__init__`.

## Versioning

Three layers, versioning different things:

| Layer | Versions | Answers |
|---|---|---|
| DVC | File contents | *Which exact data and artifacts?* |
| Git + Hydra YAML | The rules | *By what procedure were they produced?* |
| MLflow | Runs | *What happened, and how did it score?* |

The Git commit ties them together: `git checkout <hash> && dvc checkout`
restores both the rules and the exact data.

DVC is not initialised in the template. Run `task dvc:init` once in the new
project, then add a remote.

## Dependencies

Managed with [uv](https://docs.astral.sh/uv/). `pyproject.toml` declares **lower
bounds only**, so every project generated from this template resolves against
current releases:

```bash
task sync      # base + dev + notebooks + viz
task setup     # everything, including torch and mlflow
task upgrade   # move every pin forward (uv lock --upgrade)
task add -- lightgbm
```

Optional extras keep the training environment lean: `app`, `tracking`, `dvc`,
`torch`, `xgboost`, `viz`, `notebooks`, `dev`. Install what a given model or
stage actually needs.

The template ships **without** `uv.lock`. Your project should commit the lock
file `task setup` generates — that is what makes an environment reproducible.

`requires-python` is `>=3.11,<3.14`. The upper bound is the one deliberate cap:
`hydra-core` 1.3.x cannot build its argument parser on Python 3.14, which breaks
every `@hydra.main` entry point (`task train`, `task clean:data`, the DVC
pipeline). Notebooks, which use the Compose API, are unaffected. Remove the cap
once `hydra-core` supports 3.14 — uv will otherwise fetch a 3.13 interpreter
automatically.

## Commands

`task` lists everything. The ones used most:

| Command | |
|---|---|
| `task setup` | create the environment and install git hooks |
| `task lab` | start JupyterLab |
| `task clean:data` | run cleaning + split as a script |
| `task train -- models=model_a` | train one model |
| `task sweep -- models=model_a,model_b` | Hydra multirun |
| `task check` | lint and test |
| `task mlflow` | MLflow UI on `./mlruns` |
| `task dvc:repro` | reproduce the pipeline |
| `task api` / `task demo` | run the API / the Streamlit demo |

Lint includes docstring rules: the documentation standard the placeholders
follow is enforced, not just suggested.
