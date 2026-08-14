---
name: statistical-analysis
description: Rigorous statistical analysis in Python — hypothesis testing, A/B tests, confidence intervals, effect sizes, power analysis, and multiple-comparison correction (scipy.stats, statsmodels). Use this skill whenever the user wants to test whether a difference/effect is real, compare groups or models, design or analyze an A/B experiment, compute sample size, interpret p-values, or asks "is this significant", "kiểm định", "so sánh hai nhóm", "A/B test". Also trigger when the user is about to draw a conclusion from data (e.g. "model A is better than model B") without statistical backing.
---

# Statistical Analysis

Statistics is the guard rail between data and wrong conclusions. The workflow is always: define the question → check assumptions → pick the test → compute effect size + CI (not just p) → interpret honestly.

## Choosing the test

| Question | Parametric | Non-parametric (default when in doubt) |
|---|---|---|
| 2 independent group means | Welch's t-test (`ttest_ind(equal_var=False)`) | Mann-Whitney U |
| 2 paired measurements | paired t-test | Wilcoxon signed-rank |
| 3+ group means | one-way ANOVA (+ Tukey HSD post-hoc) | Kruskal-Wallis (+ Dunn) |
| 2 proportions / conversion rates | two-proportion z-test (`statsmodels.proportions_ztest`) | Fisher exact (small n) |
| Categorical association | chi-square (`chi2_contingency`) | Fisher exact |
| Correlation | Pearson | Spearman (monotonic, robust to outliers) |
| Compare 2 ML models on same test set | paired t-test on per-sample scores | Wilcoxon; McNemar for classifiers on same items |

Defaults that avoid trouble: **always Welch, never Student** (equal-variance assumption buys nothing); paired data must use paired tests (huge power difference); check normality by looking at a histogram/QQ-plot of *residuals*, not by significance tests of normality (they overpower at large n, underpower at small n). With n per group ≳ 30–50 and no wild outliers, t-tests are robust anyway.

## Never report a bare p-value

Every result must include all three:
1. **Effect size** — Cohen's d (means), risk/odds ratio or absolute lift (proportions), correlation r. p < 0.001 with d = 0.02 is "we proved a difference nobody cares about."
2. **Confidence interval** — on the effect, not on the group means separately. Bootstrap when no formula fits:
```python
from scipy.stats import bootstrap
res = bootstrap((a, b), lambda a, b, axis: a.mean(axis) - b.mean(axis),
                n_resamples=10_000, method="BCa", paired=False)
```
3. **The decision it informs** — state what the number means for the actual question.

Interpretation discipline: p is P(data this extreme | H0), NOT P(H0 true). "Not significant" ≠ "no effect" — it may be an underpowered study; look at the CI width. Statistical significance ≠ practical significance.

## A/B testing

Design BEFORE looking at data:
1. Define the primary metric and minimum detectable effect (MDE) — the smallest lift worth acting on.
2. Power analysis for sample size:
```python
from statsmodels.stats.power import NormalIndPower, TTestIndPower
n = NormalIndPower().solve_power(effect_size=es, power=0.8, alpha=0.05)
# proportions: es = proportion_effectsize(p_baseline, p_baseline + mde)
```
3. Fix the duration/sample size in advance. **Peeking** (testing repeatedly until significant) inflates false positives severely — if ongoing monitoring is required, use sequential methods (alpha-spending / mSPRT), not repeated fixed-horizon tests.
4. Randomize at the correct unit (user, not pageview — pageviews from one user are correlated) and verify with an A/A sanity check or SRM check (chi-square on assignment counts).
5. Analyze the metric at the randomization unit; for ratio metrics use the delta method or bootstrap over users.

## Multiple comparisons

Testing many hypotheses (many metrics, many segments, many model variants) at α=0.05 guarantees false positives (20 tests → ~64% chance of at least one). Correct with:
- `statsmodels.stats.multitest.multipletests(pvals, method="fdr_bh")` — Benjamini-Hochberg FDR, the sensible default for exploration.
- Bonferroni (`alpha/m`) only when any single false positive is very costly.
- Pre-register ONE primary metric; everything else is labeled exploratory.

## Classic traps to check every analysis for

- **Simpson's paradox**: aggregate trend reverses within subgroups — always check the key segments before concluding.
- **Correlation ≠ causation**: observational data supports association claims only; causal language requires randomization or causal-inference methods (DiD, IV, propensity scores — flag when the user needs these).
- **Selection/survivorship bias**: who is missing from the data? (e.g., churned users absent from a satisfaction survey).
- **Regression to the mean**: extreme groups selected on a noisy metric will look "improved" at re-measurement without any intervention.
- **Outliers driving the result**: rerun with robust alternatives (median, Mann-Whitney, trimmed means); if the conclusion flips, say so.
- **HARKing / p-hacking**: hypotheses must precede the test. Exploratory findings are hypothesis-generating and need fresh data to confirm.

## Reporting template

For each analysis produce: question → data (n, unit, exclusions) → method (test + why + assumption check) → result (effect size, 95% CI, p) → plain-language conclusion with caveats. One honest sentence beats a table of stars: "Variant B lifted conversion by 1.8pp (95% CI [0.6, 3.0], p=0.003, n=42k users); this exceeds our 1pp MDE, recommend shipping."
