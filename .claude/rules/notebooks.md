---
paths:
  - "**/*.ipynb"
  - "**/notebooks/**"
---

# The notebook leakage boundary

Notebooks in this repository are ordered, and the order encodes the leakage boundary. Read
`machine-learning/SKILL.md` for the general rule; this is how it lands in the notebook sequence.

**`01_clean_and_split` does only deterministic, model-agnostic work:** schema validation,
deduplication, dropping non-predictive columns and invalid labels, filtering on hard external
bounds, and the train/test split.

**Anything that *learns* from the data belongs in a `02x` notebook, fitted on the training split
only:** imputation, statistical outlier removal, scaling, encoding, feature engineering,
selection, dimensionality reduction.

**The deciding test is where the threshold comes from.** A bound known before seeing the data — a
physical range, a 3GPP spec limit, an age ceiling — belongs in 01. A threshold derived from the
data — a quantile, a mean, a correlation with the target — is fitted, and belongs in 02x.

**The test split is frozen from the end of 01 until notebook 03.** No notebook between them may
read it, plot it, or compute a statistic from it.

Practical notes:
- `notebooks/` is excluded from ruff. That is a formatting exemption, not a licence for
  undocumented cells.
- Do not fill in a blank section of a sectioned template notebook unless asked. The sections are
  the deliverable.
