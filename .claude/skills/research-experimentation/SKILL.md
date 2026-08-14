---
name: research-experimentation
description: Run rigorous ML/AI research experiments — controlled comparisons, ablation studies, fair baselines, multi-seed evaluation, statistical significance for papers/theses, and reproducible experiment code organization. Use this skill whenever the user is doing research or thesis work — comparing methods for a paper, designing ablations, deciding if an improvement is real, organizing experiment configs and results, mentions "ablation", "baseline", "thí nghiệm", "luận văn", "so sánh phương pháp", or reports a result from a single training run as if it were conclusive.
---

# Research Experimentation

Research results must survive three questions: Is the comparison fair? Is the effect bigger than the noise? Can someone else reproduce it? Build every experiment to answer all three by construction.

## Experimental design

- **One question per experiment**, stated before running: "Does component X improve metric M on dataset D over baseline B?" Everything else fixed.
- **Change exactly one variable** between compared runs. Method-vs-baseline comparisons where the method also got a better LR schedule, more epochs, or extra augmentation measure your tuning effort, not the method.
- **Fair baselines are a moral obligation**: tune the baseline's hyperparameters with the same budget you gave your method (same search space size, same number of trials). Most "improvements" in the literature shrink or vanish under this rule — make sure yours doesn't.
- Fixed data protocol before any method work: splits frozen and hashed, preprocessing identical across methods, test set touched only for the final table (validation drives every decision). Grouped/temporal split correctness per `ml-data-analysis`.
- Decide the **primary metric** (and its direction of "better") in advance; secondary metrics are reported, not cherry-picked post hoc.

## Noise: seeds and significance

- **Never compare single runs.** Run ≥3 seeds (5 if the gap is small); seeds vary init, data order, and augmentation. Report mean ± std everywhere.
- An improvement smaller than the seed-to-seed std of either method is not a finding — it's noise with a narrative.
- Significance for the headline comparison: paired test on per-seed scores (paired t-test or Wilcoxon; same seeds used for both methods = paired). For per-sample metrics on a fixed test set, paired bootstrap over test items gives CIs on the gap. See `statistical-analysis` for mechanics.
- Beware **graduate student descent**: iterating on the validation/test set until numbers improve overfits your process to the data. Keep a truly-final test evaluation count of one; if the dataset has a public leaderboard ethic, honor it privately too.

## Ablations

Ablations answer "which parts matter and how much":
- **Leave-one-out** from the full method: full model, then remove each component individually. Add-one-in from the baseline when components interact strongly.
- Ablate everything a reviewer would ask about: each architectural component, each loss term (λ→0), each data/augmentation choice, key hyperparameters (sensitivity curves: metric vs λ over a grid).
- Same seeds, same budget, same protocol as the main results. An ablation table with single runs is decoration.
- Report ablations that DIDN'T matter too — "we tried X, it changed nothing" is informative and honest, and preempts reviewer suggestions.
- Sanity ablations that catch bugs: shuffled labels (should destroy performance — if not, leakage), random features (should hurt), trivial baseline in every table (mean predictor / majority class / nearest-neighbor).

## Code & config organization

One run = one config = one results directory. No exceptions.

```
project/
  configs/            # yaml/dataclass per experiment; base + overrides
  src/                # library code (models, data, training) — no experiment logic
  scripts/train.py    # entry: python scripts/train.py --config configs/dann_l03.yaml --seed 42
  results/
    dann_l03_s42/     # config copy, git hash, metrics.json, checkpoints, logs
  notebooks/          # analysis ONLY — reads results/, never trains
```

- The entry script snapshots into the run dir: full resolved config, git commit hash (+ dirty flag), environment (`pip freeze`/`uv lock`), seed, dataset version/hash. A result you can't trace to exact code+config+data is a rumor.
- Configs compose: `base.yaml` + experiment overrides; the diff between two configs documents the experiment.
- Never modify library code per-experiment ("temporarily comment out the norm layer") — every variant is a config flag. Untracked code edits are how results become unreproducible mysteries.
- Name runs semantically (`dann_lambda0.3_seed42`), log to MLflow/W&B in addition to the run dir (see `pytorch-training-debugging`), and keep a lab-notebook file: date, hypothesis, runs launched, observation, next step. Future-you writing the thesis will need it desperately.

## Analysis & reporting

- Results tables: mean ± std over seeds, best per column in bold, trivial baseline included, sample sizes/seeds stated in the caption. Match precision to noise (std 0.8 → reporting 71.23 is false precision; write 71.2 ± 0.8).
- Learning curves (metric vs data size) and sensitivity curves (metric vs key hyperparameter) often say more than a single-number table — include them for the main claims.
- **Negative-result forensics before abandoning an idea**: is the implementation correct (overfit-one-batch test)? Is the effect masked by a bottleneck elsewhere? Is the metric sensitive enough? Many "method doesn't work" conclusions are "method has a bug."
- **Positive-result forensics before believing one**: check for leakage, check the baseline is properly tuned, check per-slice results (is the gain broad or one weird slice?), rerun with fresh seeds. Extraordinary improvements are usually bugs; the feeling of excitement is a trigger for verification, not celebration.
- Error analysis: read actual failure cases of both your method and the baseline; characterize WHERE the improvement comes from — this becomes the analysis section reviewers love and is often where the real insight lives.

## Compute budgeting

- Pilot at small scale first (subset of data, smaller model, fewer epochs) to debug the pipeline and estimate effect sizes; scale up only experiments whose pilot signal justifies it.
- Fixed-budget comparisons: equal wall-clock or equal FLOPs across methods, stated explicitly — "our method is better after 10× the training" is a different (weaker) claim.
- Queue discipline: maintain a prioritized experiment list; before launching anything ask "what decision does this result change?" If no decision depends on it, don't burn the GPU-hours.
