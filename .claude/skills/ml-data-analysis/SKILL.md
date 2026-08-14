---
name: ml-data-analysis
description: Rigorous exploratory data analysis (EDA) and data preparation for machine learning projects in Python (pandas, numpy, seaborn). Use this skill whenever the user wants to explore, clean, profile, or prepare a dataset for training — including loading CSVs/parquet, handling missing values and outliers, feature engineering, train/val/test splitting, or building preprocessing pipelines. Also trigger when the user mentions "EDA", "phân tích dữ liệu", "data cleaning", "feature engineering", "data leakage", or asks why a model performs suspiciously well or poorly, since data issues are the usual cause.
---

# ML Data Analysis & Preparation

The quality of an ML model is bounded by the quality of its data pipeline. This skill enforces a disciplined EDA → clean → split → transform workflow that prevents the two most expensive failure modes: silent data corruption and data leakage.

## Workflow

Always follow this order. Splitting BEFORE fitting any transformation is non-negotiable.

1. Profile the raw data
2. Define the prediction task and unit of generalization
3. Split (respecting groups/time)
4. Clean and transform (fit on train only)
5. Sanity-check the result

## 1. Profile before touching anything

Run a profiling pass and show the user the results before making decisions:

```python
df.shape, df.dtypes, df.memory_usage(deep=True).sum() / 1e6
df.isna().mean().sort_values(ascending=False)   # missing rate per column
df.describe(include="all").T
df.duplicated().sum()
df[num_cols].skew()                              # candidates for log-transform
```

Check for these specific traps:
- **Sentinel values masquerading as data**: -999, -120, 0, 9999, empty strings. Plot histograms; a spike at a round number at the edge of the range is almost always a fill value, not a measurement. Confirm with the user or domain spec before treating it as real.
- **Mixed dtypes in one column** (`object` dtype on a numeric-looking column) — usually stray strings like "N/A" or thousands separators.
- **Duplicated rows vs. duplicated entities**: `df.duplicated()` only catches exact rows. Also check `df.duplicated(subset=entity_keys)`.
- **Physically impossible values**: apply domain range checks (e.g., LTE RSRP must lie in [-140, -44] dBm per 3GPP TS 36.133; ages > 120; negative durations). Ask the user for the valid ranges if unknown.
- **Class imbalance / target distribution**: `df[target].value_counts(normalize=True)` or histogram for regression targets.

For datasets too large for memory, use `pd.read_csv(..., nrows=100_000)` for profiling, `dtype` downcasting (`float64→float32`, `int64→int32`, categorical for low-cardinality strings), or switch to polars/parquet.

## 2. Define the unit of generalization

Before splitting, ask: **what must the model generalize across?** New users? New locations? Future time? The split must mirror deployment:

| Deployment reality | Correct split |
|---|---|
| New independent samples | random `train_test_split` (stratify on target if classification) |
| New users/devices/sessions | `GroupShuffleSplit` / `GroupKFold` on the entity ID |
| Future time | temporal split — train on past, test on future, never shuffle |
| New geographic regions | spatial blocking (split by region/grid cell) |

A random split on grouped data leaks: samples from the same user appear in both train and test, and the model memorizes users instead of learning the task. This inflates test metrics by a large margin and is the #1 cause of "great offline, terrible in production."

## 3. Leakage checklist

Fit ALL of these on the training set only, then apply to val/test:
- Scalers/normalizers (`StandardScaler`, min-max)
- Imputers (mean/median fill values)
- Encoders (target encoding is especially dangerous — use out-of-fold)
- Feature selection (correlation with target, mutual information)
- Dimensionality reduction (PCA, UMAP)

Use `sklearn.pipeline.Pipeline` + `ColumnTransformer` so fit/transform boundaries are structural, not manual discipline:

```python
pre = ColumnTransformer([
    ("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                      ("sc", StandardScaler())]), num_cols),
    ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
])
# pre.fit(X_train) only; pre.transform(X_val)
```

Also audit **feature-level leakage**: any column computed from information unavailable at prediction time (post-outcome timestamps, aggregate stats that include the row itself, IDs correlated with the target). If a single feature gives near-perfect accuracy, be suspicious, not happy.

## 4. Missing values and outliers

- Distinguish **missing-at-random** from **structurally missing** (e.g., a sensor out of range). Structural missingness is information — encode it as an explicit binary mask/indicator column rather than silently imputing.
- Median imputation for skewed numerics, mean for symmetric, mode or "MISSING" category for categoricals. For models that handle NaN natively (LightGBM, XGBoost), often best to leave NaN as-is.
- Outliers: plot first (`sns.boxplot`, log-scale histograms). Clip (`df[col].clip(lo, hi)`) using train-set quantiles (e.g., 0.5%–99.5%) rather than dropping rows, unless the row is provably corrupt.

## 5. Visualization defaults

Use seaborn with a consistent, publication-friendly config:

```python
sns.set_theme(style="whitegrid", context="notebook")
```

- Distributions: `sns.histplot(..., kde=True)`; compare train vs test distributions on the same axes to detect covariate shift.
- Relationships: `sns.scatterplot` with `alpha=0.3` for dense data; `sns.heatmap(df[num_cols].corr(), annot=False, cmap="coolwarm", center=0)` for correlations.
- Target vs feature: `sns.boxplot`/`violinplot` for categorical features, binned means for numeric.
- Always label axes with units and state the sample size in the title or caption.

## 6. Sanity checks before handing to the model

- Re-check shapes and dtypes after every transform; assert no NaN/inf in the final arrays: `assert np.isfinite(X).all()`.
- Verify split sizes and that group/time constraints hold: `assert set(train_ids) & set(test_ids) == set()`.
- Train a trivial baseline (mean predictor / majority class / logistic regression) and record its score. Every later model must beat this; if a deep model doesn't, the problem is the pipeline, not the architecture.
- Save the exact preprocessing artifacts (`joblib.dump(pre, ...)`) and the split indices — they are part of the model.

## Output conventions

When performing EDA for a user, produce: (1) a short findings summary in prose — data size, missing patterns, anomalies found, leakage risks; (2) the cleaning decisions taken and why; (3) reusable code as a script or notebook cells, not ad-hoc fragments. Flag every assumption that needs domain confirmation instead of silently deciding.
