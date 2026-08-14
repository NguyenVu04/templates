---
name: ml-interpretability
description: Explain and audit machine learning models — SHAP, permutation importance, partial dependence, error analysis by slice, and basic fairness checks. Use this skill whenever the user wants to understand why a model makes its predictions, which features matter, explain a single prediction to a stakeholder, debug unexpected model behavior, detect leakage or spurious correlations via importances, or check whether a model treats subgroups differently ("giải thích model", "feature importance", "tại sao model dự đoán", model audit, XAI).
---

# ML Interpretability

Interpretability answers three distinct questions — always identify which one the user is asking: (1) *globally*, what drives this model? (2) *locally*, why this prediction for this instance? (3) *diagnostically*, where and for whom does the model fail?

## Global importance

**Permutation importance** (model-agnostic, honest default): shuffle one feature, measure metric drop, **on the validation/test set** — train-set importance rewards memorization.
```python
from sklearn.inspection import permutation_importance
r = permutation_importance(model, X_val, y_val, n_repeats=10, random_state=0)
```
Caveat: correlated features share/steal importance — permuting one while its twin remains lowers both scores. Cluster correlated features (hierarchical clustering on Spearman corr) and permute groups, or interpret with the correlation structure in view.

Prefer permutation/SHAP over impurity-based `feature_importances_` of tree ensembles — impurity importance is biased toward high-cardinality features and computed on train.

**SHAP** (consistent, direction-aware):
```python
import shap
explainer = shap.TreeExplainer(model)          # trees: fast, exact
# shap.Explainer(model.predict, X_bg) for model-agnostic (slower)
sv = explainer(X_val)
shap.plots.beeswarm(sv)     # global: importance + direction + distribution
shap.plots.scatter(sv[:, "age"])   # dependence + interactions
```
Read the beeswarm: position = impact on output, color = feature value; a red-right/blue-left pattern means "high value pushes prediction up." For deep/tabular PyTorch models use KernelSHAP on a sample or Captum (IntegratedGradients).

## Local explanations

`shap.plots.waterfall(sv[i])` decomposes one prediction: base value (average output) + per-feature contributions = model output. This is the right artifact for "why was this customer scored high-risk?" Translate to prose for stakeholders: name the top 3 contributors with direction and rough magnitude; never present raw SHAP values without units/context.

Honesty requirements: SHAP explains **the model, not reality** — "the model relies on X" is not "X causes y." With correlated features, SHAP can spread credit across proxies. Say so when it matters.

## Effects: PDP and ICE

```python
from sklearn.inspection import PartialDependenceDisplay
PartialDependenceDisplay.from_estimator(model, X_val, ["age", ("age", "income")], kind="both")
```
PDP shows the average effect of a feature; ICE lines show per-instance effects — diverging ICE lines mean interactions that the PDP average hides. PDP extrapolates into unrealistic feature combinations when features are correlated; don't over-read regions with little data (plot the rug/deciles).

## Interpretability as a debugging tool

Run these checks on every serious model — they catch bugs metrics can't:
- **Leakage detector**: one feature dominating importance (>50% of total) or a feature that "shouldn't" matter ranking top-3 → inspect how it was built; it often encodes the target or post-outcome information.
- **Spurious correlation**: importance on ID-like columns, row order, timestamps in a non-temporal task.
- **Sanity direction check**: do dependence plots match domain knowledge sign? (price ↑ → demand ↓). Violations are either discoveries or bugs — usually bugs.
- **Model comparison**: when a new model wins, compare importances with the old one; a win driven by a new weird feature deserves suspicion, not celebration.

## Error analysis by slice

Aggregate metrics hide localized failure. Build a slice table:
```python
df_eval["err"] = np.abs(df_eval.y_true - df_eval.y_pred)   # or per-sample loss / correct flag
df_eval.groupby("segment")[["err"]].agg(["mean", "median", "count"])
```
- Slice by: important categoricals, binned numerics, time period, data source/domain, and prediction confidence.
- Then read the worst slice's actual failing examples — 20 concrete examples generate hypotheses that no chart will.
- Cluster errors: embed inputs (or use feature vectors), cluster the high-error points, characterize each cluster. Systematic error clusters → targeted data collection or features; uniform noise → you may be at the Bayes limit.
- Track slice metrics across model versions; regressions in a key slice can hide inside an improved average.

## Basic fairness checks

When predictions affect people, compute per-group (sensitive attribute or proxy): positive/selection rate, TPR, FPR, precision, calibration. Large TPR/FPR gaps mean the model errs differently across groups even at equal accuracy. Note the impossibility result: calibration and error-rate parity generally can't hold simultaneously with different base rates — the right fairness criterion is a product/policy decision; the analyst's job is to surface the trade-off with numbers. Removing the sensitive column does NOT remove bias (proxies remain); measure outcomes, don't assume blindness.

## Reporting

An interpretability report contains: global top-10 importance (with method + dataset stated), 2–3 dependence plots of key features with domain commentary, 1–2 local explanations of representative/interesting cases, slice table with the worst slices highlighted, and explicit caveats (correlation clusters, model-not-reality). Match depth to audience: stakeholders get the prose story; the appendix gets the beeswarm.
