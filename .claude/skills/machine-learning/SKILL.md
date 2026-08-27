---
name: machine-learning
description: >-
  The full classical-ML and PyTorch lifecycle — exploratory data analysis and leakage-safe
  splitting, model architecture, training loops and debugging, interpretability and error
  analysis, evaluation and deployment, research experiments and ablations, and the statistics
  that decide whether a difference is real. This SKILL.md is the router: identify the phase,
  then read ONLY the relevant reference file before writing code.
when_to_use: >-
  Use whenever the user explores, cleans or splits a dataset ("EDA", "phân tích dữ liệu", "data
  cleaning", "feature engineering", "data leakage"); designs or reviews a PyTorch model (MLP,
  CNN, Transformer, attention, embeddings, custom layers, losses, "thiết kế mô hình", "kiến trúc
  mạng"); trains one or hits training trouble ("training loop", "huấn luyện model", "loss không
  giảm", loss is NaN, overfitting, val metrics suspiciously good, "CUDA OOM", training too slow,
  not reproducible); explains a model ("giải thích model", "feature importance", "tại sao model
  dự đoán", SHAP, model audit, XAI, fairness by subgroup); evaluates, exports or serves a trained
  model ("triển khai model", "deploy", inference endpoint, ONNX/TorchScript, quantization, drift
  monitoring); runs research experiments ("ablation", "baseline", "thí nghiệm", "luận văn",
  "so sánh phương pháp", reporting a single run as conclusive); or needs statistics on any
  comparison ("is this significant", "kiểm định", "so sánh hai nhóm", "A/B test", p-values,
  confidence intervals, effect size, sample size).
---

# Machine Learning (Data · PyTorch · Experiments)

A complete playbook for building models that generalize and results that survive scrutiny. This
SKILL.md is the router: classify the task, then read only the reference files it points at.

## Phase routing table

| The user wants to... | Read |
|---|---|
| Profile, clean, split or transform a dataset; build preprocessing pipelines; chase a leakage suspicion | `references/data.md` |
| Design or review an architecture — modules, layers, losses, DataLoaders, parameter count, GPU memory | `references/model-design.md` |
| Write or debug a training pipeline — loops, optimizers, schedules, AMP, checkpoints, reproducibility, tracking | `references/training.md` |
| Understand or audit a trained model — importances, SHAP, PDP/ICE, error analysis by slice, fairness | `references/interpretability.md` |
| Do the final evaluation, export, serve, containerize, optimize inference, monitor for drift | `references/deployment.md` |
| Compare methods rigorously — controlled experiments, fair baselines, ablations, multi-seed runs, thesis/paper work | `references/experimentation.md` |
| Decide whether a difference is real — hypothesis tests, CIs, effect sizes, power, A/B tests, multiple comparisons | `references/statistics.md` |

The last two are cross-cutting: any claim that A beats B pulls in `experimentation.md` (was the
comparison fair?) and `statistics.md` (is the gap bigger than the noise?), whatever phase
produced it.

## The leakage boundary

The single rule that governs every phase. Split first, then fit — and the test split stays
frozen until the end.

**Deterministic, model-agnostic work may happen before the split:** schema validation,
deduplication, dropping non-predictive columns and invalid labels, filtering on hard external
bounds, and the split itself.

**Anything that *learns* from the data happens after the split, fitted on train only:**
imputation, statistical outlier removal, scaling, encoding, feature selection, dimensionality
reduction, feature engineering.

The test that decides which side a step falls on is **where the threshold comes from**. A bound
known before seeing the data (a physical range, a spec limit) is deterministic. A threshold
derived from the data (a quantile, a mean, a correlation) is fitted, and belongs after the split.

Two corollaries:
- **The split must mirror deployment.** New users → group split. Future time → temporal split.
  New regions → spatial blocking. A random split on grouped data inflates test metrics badly and
  is the #1 cause of "great offline, terrible in production."
- **The test set is scored exactly once**, at the end, with the checkpoint chosen by validation.
  Re-running test after a change turns it into a second validation set.

## Non-negotiable defaults

1. **Overfit a tiny subset first.** 1–2 batches, several hundred steps, loss → ~0. If it can't,
   there is a bug and a full run is wasted GPU time.
2. **Score the trivial baseline before anything else** — mean predictor, majority class, logistic
   regression, LightGBM on tabular. Every later model must beat it; if a deep model doesn't, the
   problem is the pipeline, not the architecture.
3. **Seed everything and log the seed.** Report mean ± std over ≥3 seeds. A single run is not a
   result, and two single runs are not a comparison.
4. **Checkpoints carry model + optimizer + scheduler + epoch + config + metric**, not just
   weights. Select by validation metric.
5. **Every run records** config, git commit, dataset version and split hash, seed, environment,
   per-epoch metrics — enough to relaunch it from its own log.
6. **Suspicion is the correct response to a great number.** A feature giving near-perfect accuracy
   is a leak until proven otherwise.
7. **Fit/transform boundaries are structural, not disciplinary** — `Pipeline` +
   `ColumnTransformer`, serialized together with the model, so evaluation and serving can only
   `transform`.

## Debugging order

1. **The data and the split.** Most "model" problems are data problems, and most miraculous
   results are leaks. Start at `references/data.md`.
2. **The overfit test.** Distinguishes a bug from a tuning problem in minutes.
3. **The training loop** — gradients flowing, `train()`/`eval()` toggled, loss/target pairing,
   shapes. See `references/training.md`.
4. **The hyperparameters**, learning rate first, in decreasing order of impact.
5. **The architecture.** Last. It is rarely the reason.

## Related skills

- `ai-engineering` — anything built on top of LLMs. Fine-tuning an open-weight model, RAG,
  agents, and LLM-specific evaluation live there, not here.
- `fastapi-lifecycle` — the API that serves the model (`references/deployment.md` covers the
  model side; that skill covers the service side).
- `devops-engineering` — containers, GPUs in Kubernetes, CI/CD, monitoring infrastructure.
