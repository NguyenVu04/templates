---
paths:
  - "machine-learning/**/*.py"
  - "**/train*.py"
  - "**/configs/**/*.yaml"
---

# Training and experiment discipline

Read `machine-learning/SKILL.md` before writing training code. These are the rules a hook or a
reviewer will actually check.

## Reproducibility

- Seed `random`, `numpy` and `torch` (plus `cuda.manual_seed_all`), pass a seeded `Generator` to
  any shuffling `DataLoader`, and **log the seed with the run**.
- Every run records: full config, git commit, dataset version and split hash, seed, environment
  (`torch.__version__`, GPU), and per-epoch metrics. Log the config as a YAML/JSON artifact so
  the run can be relaunched from its own log alone.
- Name runs semantically (`dann_lambda0.3_seed42`), never by timestamp.

## Claims

- **≥3 seeds before any comparison is called real**; report mean ± std. A single run is an
  anecdote. Two single runs are not a comparison — see `references/experimentation.md` and
  `references/statistics.md` under the `machine-learning` skill.
- **The test set is scored exactly once**, at the end, with the checkpoint selected by
  validation. Files matching the frozen-split patterns are write-protected by a `PreToolUse`
  hook; if you have a legitimate reason to regenerate a split, say so and ask.
- Change one variable per run and diff against the baseline.

## Mechanics

- Checkpoints carry model + optimizer + scheduler + epoch + config + metric.
- Run the overfit-one-batch test before launching a full run.
- Log per-term losses separately in multi-loss setups; an aggregate hides which term misbehaves.

## Configuration (this repository's Hydra layout)

- Hydra composes `configs/config.yaml` from `configs/data.yaml` plus exactly one
  `configs/models/*.yaml`. Split configuration, `val_size` included, lives in `configs/data.yaml`
  and nowhere else.
- Model configs keep `model:` (constructor arguments), `optim:` and `train:` in separate groups,
  because `instantiate()` passes `model:` straight to `__init__`.
- In notebooks the `@hydra.main` decorator does not work — use the Compose API through
  `src.config.load_config()`.
- `src/data/split.py` and `src/evaluation/metrics.py` are authoritative. Every notebook and
  script uses them; models validated on different folds or scored with differently defined
  metrics cannot be compared, and the comparison is the point.
