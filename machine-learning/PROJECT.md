# Project Structure

This document describes the directory layout, the responsibility of each component, and the conventions that must be followed when working on this project.

The structure is designed around three principles:

1. **No data leakage.** Anything that *learns* from data (imputers, scalers, encoders, statistical outlier thresholds) is fitted on the training split only. The test split is frozen from the moment it is created until final evaluation.
2. **Fair model comparison.** Every model is trained and evaluated under identical conditions. Data splitting and evaluation metrics live in shared modules and are never reimplemented per model.
3. **Reproducibility.** Two questions must always be answerable for any result: *which data was used* (DVC) and *by what rules was it produced* (Git + Hydra YAML).

---

## Directory Layout

```
project-root/
├── data/
│   ├── raw/                    # Immutable source data — never modified
│   ├── interim/                # Partially processed intermediates
│   ├── processed/              # Clean, split data — output of notebook 01
│   └── external/               # Third-party / reference data
│
├── notebooks/
│   ├── 00_eda.ipynb
│   ├── 01_clean_and_split.ipynb
│   ├── 02a_xgboost.ipynb
│   ├── 02b_set_transformer.ipynb
│   ├── 02c_dann.ipynb
│   └── 03_evaluation.ipynb
│
├── src/
│   ├── __init__.py
│   ├── config.py               # Config loading / validation helpers
│   ├── data/
│   │   ├── __init__.py
│   │   ├── load.py             # Read raw data and notebook-01 outputs
│   │   ├── clean.py            # Model-agnostic cleaning logic
│   │   ├── split.py            # ★ SHARED — train/val/test splitting
│   │   └── schema.py           # Schema and constraint validation
│   ├── models/
│   │   ├── __init__.py         # Imports model modules to trigger registration
│   │   ├── base.py             # Common model interface (Protocol / ABC)
│   │   ├── xgboost.py          # Preprocessing + fit + predict for XGBoost
│   │   ├── set_transformer.py
│   │   ├── dann.py
│   │   └── wknn.py
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── metrics.py          # ★ SHARED — metric definitions
│   │   └── analysis.py         # Error analysis, calibration, feature importance
│   └── utils/
│       ├── __init__.py
│       ├── seed.py             # Global seed control
│       ├── io.py               # Save/load artifacts (preprocessor + model)
│       └── tracking.py         # MLflow wrapper
│
├── configs/
│   ├── config.yaml             # Hydra entrypoint — composes data + model
│   ├── data.yaml               # Paths, schema, constraints, split scheme
│   └── models/
│       ├── xgboost.yaml
│       ├── set_transformer.yaml
│       └── dann.yaml
│
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI entrypoint and routes
│   │   ├── schemas.py          # Pydantic request/response models
│   │   ├── inference.py        # Model loading and prediction
│   │   └── dependencies.py
│   ├── demo/
│   │   └── streamlit_app.py
│   └── Dockerfile
│
├── models/                     # Serialized artifacts (DVC-tracked)
├── reports/
│   ├── figures/
│   └── results/
├── tests/
├── mlruns/                     # Local MLflow tracking store (gitignored)
│
├── dvc.yaml                    # DVC pipeline definition (project root)
├── .dvc/
├── .gitignore
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Notebooks

Notebooks **orchestrate, visualize, and narrate**. Reusable logic belongs in `src/` so it can be imported, tested, and shared across models.

Numbering is spaced (`00`, `01`, `02x`, `03`) so intermediate steps can be inserted without renaming the whole sequence.

| Notebook | Responsibility |
|---|---|
| `00_eda.ipynb` | Exploratory analysis. Understand distributions, missingness, and data quality. Produces insights, not artifacts. |
| `01_clean_and_split.ipynb` | Model-agnostic cleaning and the train/test split. See rules below. |
| `02a_xgboost.ipynb`, `02b_set_transformer.ipynb`, … | One notebook per model. Model-specific preprocessing, feature engineering, architecture, tuning, training, and validation-set analysis. |
| `03_evaluation.ipynb` | Final comparison of all models on the held-out test set. |

Model notebooks are named `02{letter}_{model_name}` — the number already implies "model", so no `model_` prefix is needed.

### The 01 / 02x boundary

This is the most important rule in the project. It determines whether results are trustworthy.

**Notebook 01 — model-agnostic and deterministic only:**

- Schema and dtype validation
- Duplicate record removal
- Dropping non-predictive columns (record IDs, etc.)
- Dropping records with missing or invalid labels
- Dropping records that violate **hard, externally known constraints** — physical or specification bounds, e.g. a signal metric outside the range defined by the relevant standard, or coordinates outside the surveyed area
- Train/test split

**Notebook 02x — anything that learns from data:**

- Imputation of missing values
- **Statistical** outlier detection (IQR, z-score, isolation forest)
- Scaling, encoding, transformation
- Feature engineering and selection
- Train/validation split (via the shared splitter), model definition, tuning, training

**Outlier handling — the distinction that matters:**

| Type | Criterion | Where |
|---|---|---|
| Invalid record | Violates a bound known *before* seeing the data (standard, spec, physical limit) | 01 |
| Statistical outlier | Threshold derived *from* the data (mean, std, quantile) | 02x |

Using any data-derived threshold in notebook 01 leaks test-set information into the filtering decision. If a bound is used in 01, its source must be documented in `configs/data.yaml`.

### Test-set discipline

The test split is created at the end of notebook 01 and is **not touched again until notebook 03**. Preprocessing objects fitted in a `02x` notebook must be serialized together with the model, so that notebook 03 and the serving layer only call `transform` — never `fit`.

```python
# End of 02x — persist the fitted preprocessing together with the model
save_artifact({"preprocessor": preproc, "model": model}, "models/xgboost.pkl")
```

---

## `src/`

`src/` contains importable, testable logic. Notebooks import from it; it never imports from notebooks.

### `src/data/`

Model-agnostic data handling — the code behind notebook 01.

- `load.py` — read raw data and the cleaned outputs of notebook 01
- `clean.py` — deduplication, invalid-record filtering, column dropping
- `schema.py` — enforce the schema and constraints declared in `configs/data.yaml`
- `split.py` — **shared splitting logic, used by every model**

`split.py` is authoritative. Every notebook and script obtains its train/val/test splits from it, using the scheme and seed declared in `configs/data.yaml`. Splitting must respect grouping so that records belonging to the same entity (e.g. the same trajectory or device) never appear on both sides of a split — a plain random or stratified split would leak information across the boundary.

### `src/models/`

One module per model. Each module owns everything that genuinely differs between models: its own preprocessing, feature engineering, training loop, and prediction logic. There is deliberately **no shared `features/` package** — model-specific transforms live with the model that requires them.

**What each model module must *not* implement itself:**

| Component | Location | Reason |
|---|---|---|
| Train/val/test splitting | `src/data/split.py` | Models validated on different folds cannot be compared |
| Evaluation metrics | `src/evaluation/metrics.py` | Divergent metric definitions make the results table meaningless |

**Common interface.** Every model exposes the same surface so that training and evaluation code is written once:

```python
class BaseModel(Protocol):
    def fit(self, X_train, y_train, X_val=None, y_val=None): ...
    def predict(self, X): ...
    def save(self, path): ...      # persists preprocessor + model together
    def load(self, path): ...
```

Internals may differ completely — a single `.fit()` call for gradient boosting, a full epoch loop with a gradient reversal layer for adversarial domain adaptation — as long as the interface holds. This lets notebook 03 iterate over all models uniformly:

```python
for name in ["xgboost", "set_transformer", "dann"]:
    model = load_artifact(f"models/{name}.pkl")
    preds = model.predict(X_test)          # same test set
    results[name] = evaluate(preds, y_test) # same metric function
```

**Model resolution.** Models are instantiated from config using Hydra's `_target_` mechanism. A separate registry module is intentionally omitted, since `_target_` already provides name-to-class resolution; maintaining both would duplicate the same responsibility.

```python
from hydra.utils import instantiate
model = instantiate(cfg.models)
```

### `src/evaluation/`

- `metrics.py` — the single definition of each metric, shared by all models
- `analysis.py` — error analysis, calibration, feature importance, comparison plots

### `src/utils/`

- `seed.py` — set seeds across Python, NumPy, and the DL framework
- `io.py` — serialize and load artifacts (always preprocessor + model together)
- `tracking.py` — thin MLflow wrapper (see below)

---

## `configs/`

Configuration is separated from code so that experiments can be varied without editing source. Hydra composes the final config at runtime.

### `configs/config.yaml`

The entrypoint. It declares which data and model configs to compose.

```yaml
defaults:
  - data
  - models: xgboost
  - _self_

seed: 42
project_name: <project-name>

mlflow:
  tracking_uri: ./mlruns
  experiment_name: <project-name>
```

### `configs/data.yaml`

A **single file**, versioned by Git. Manual `v1.yaml`, `v2.yaml` files are not used — Git history already provides versioning, and duplicating it produces dead files.

This file is the single source of truth for the schema, the validity constraints, and **all split configuration** — including the validation split.

```yaml
raw_path: data/raw/dataset.parquet
processed_path: data/processed/clean

split:
  method: group_shuffle
  group_col: <grouping-column>
  seed: 42
  test_size: 0.2
  val_size: 0.2          # kept here, not in model configs

schema:
  columns:
    <feature>: {dtype: float64, min: <lower>, max: <upper>, nullable: false}
    <group_col>: {dtype: int64, nullable: false}
```

`val_size` and the validation split scheme live here rather than in individual model configs. If each model defined its own validation split, models would tune and early-stop against different data, and their scores would no longer be comparable.

`schema.py` is the component that *enforces* these declarations. The YAML declares data; the Python module holds the logic. If constraints later require cross-column or conditional rules, express them in `schema.py` (e.g. with a schema-validation library) rather than expanding the YAML into a rule engine.

### `configs/models/*.yaml`

One file per model, containing the instantiation target, the tuned hyperparameters, training settings, and the artifact path. Keys are grouped so that `_target_` instantiation receives only architecture arguments.

```yaml
_target_: src.models.set_transformer.SetTransformerModel

model:                      # architecture — passed to __init__
  dim_hidden: 128
  num_heads: 4
  dropout: 0.1

optim:                      # tuned hyperparameters
  lr: 3.0e-4
  weight_decay: 1.0e-5

train:                      # training procedure
  batch_size: 64
  max_epochs: 100
  early_stopping_patience: 10

artifact_path: models/set_transformer.pkl
```

Grouping matters: if `batch_size` sat at the same level as `dim_hidden`, Hydra would attempt to pass it to the model constructor. Keeping `model:`, `optim:`, and `train:` separate keeps that boundary clean.

### Usage

```bash
python -m src.models.train models=set_transformer
python -m src.models.train --multirun models=xgboost,set_transformer,dann
```

In notebooks, use the Compose API — the `@hydra.main` decorator does not work in Jupyter:

```python
from hydra import compose, initialize
with initialize(config_path="../configs", version_base=None):
    cfg = compose(config_name="config", overrides=["models=xgboost"])
```

---

## Versioning: DVC, Git, and Hydra

These layers version **different objects** and are complementary, not redundant.

| Layer | Versions | Answers |
|---|---|---|
| **DVC** | File *contents* (checksums of parquet, pickle) | "Which exact data and artifacts?" |
| **Git + Hydra YAML** | The *rules* (schema, constraints, split scheme, seed, hyperparameters) | "By what procedure were they produced?" |

Reproducibility requires both answers. DVC does not know the split scheme; the YAML does not store the data.

**The linkage is the Git commit.** A single commit pins the config, the DVC pointers, and the code together:

```
git checkout <hash> && dvc checkout
```

restores both the rules and the exact data contents of that run.

### `dvc.yaml`

Lives at the **project root**, not inside `configs/` — DVC looks for it there by convention. It points directly at `configs/data.yaml` for its parameters, so split settings are declared exactly once and consumed by both Hydra and DVC. A separate `params.yaml` is therefore not needed.

```yaml
stages:
  clean_split:
    cmd: python -m src.data.clean
    deps:
      - src/data/clean.py
      - data/raw/dataset.parquet
    params:
      - configs/data.yaml:
          - split.test_size
          - split.group_col
          - split.seed
    outs:
      - data/processed/clean.parquet
```

Changing a tracked parameter causes `dvc repro` to rerun the affected stages and everything downstream.

---

## Experiment Tracking: MLflow

MLflow is the experiment tracker and, optionally, the model registry. It requires no change to the directory layout — only a dependency, a config block, and a wrapper module.

**Wrap it.** Training code calls `src/utils/tracking.py` rather than the MLflow API directly, so the tracker can be swapped or extended by editing one file:

```python
# src/utils/tracking.py
import mlflow

def start_run(cfg):
    mlflow.set_tracking_uri(cfg.mlflow.tracking_uri)
    mlflow.set_experiment(cfg.mlflow.experiment_name)
    return mlflow.start_run()

def log_config(cfg): ...
def log_metrics(d, step=None): ...
```

**Log manually, not with `autolog`.** Framework-specific autologging records different parameters and metrics for gradient boosting than for a PyTorch model, which undermines like-for-like comparison. Log the shared metrics from `src/evaluation/metrics.py` explicitly so every run is measured identically. Autologging may be enabled as a supplement, never as the primary record.

**Registry is optional.** MLflow's Model Registry manages a model's lifecycle (staging, promotion, load-by-stage) — a concern DVC does not cover, since DVC versions artifacts by content against a Git commit. For a research project where the goal is comparing models, content versioning via DVC is usually sufficient. Enable the registry when models move into serving.

---

## `app/`

Serving and demonstration code, kept separate from `src/` for two reasons: `src/` is pure ML logic, and the app carries dependencies (FastAPI, Streamlit) that should not pollute the training environment.

**Dependency direction is one-way: `app/` imports from `src/`, never the reverse.**

`inference.py` loads the serialized artifact produced by a `02x` notebook and applies the *same* fitted preprocessing used during training, which is what prevents train/serve skew:

```python
from src.utils.io import load_artifact

artifact = load_artifact("models/set_transformer.pkl")

def predict(features):
    X = artifact["preprocessor"].transform(features)   # transform, never fit
    return artifact["model"].predict(X)
```

Serving dependencies are declared as an optional group so the training environment stays lean:

```toml
[project.optional-dependencies]
app = ["fastapi", "uvicorn", "streamlit", "pydantic"]
tracking = ["mlflow"]
dev = ["pytest", "ruff", "pre-commit"]
```

```bash
uv pip install -e .              # training only
uv pip install -e ".[app]"       # with serving
```

---

## Conventions Summary

| Rule | Rationale |
|---|---|
| `data/raw/` is never modified | Source of truth; all transforms write new files |
| Notebook 01 contains no data-derived thresholds | Prevents leakage into filtering decisions |
| Splitting comes from `src/data/split.py` | Guarantees identical folds across all models |
| Metrics come from `src/evaluation/metrics.py` | Guarantees identical measurement across all models |
| Split configuration lives in `configs/data.yaml` | Single source of truth for train/val/test |
| Test set is untouched until notebook 03 | Preserves the validity of the final estimate |
| Preprocessor is serialized with the model | Evaluation and serving transform, never refit |
| All models implement `fit` / `predict` / `save` / `load` | Uniform training and evaluation code |
| Notebooks orchestrate; `src/` holds logic | Reuse, testing, and protection against drift |
| `app/` depends on `src/`, never the reverse | Clean layering; keeps the ML core independent |
| Data and model artifacts are DVC-tracked, not committed | Repository stays small; contents remain reproducible |
| Seeds are set through `src/utils/seed.py` | Reproducible runs |