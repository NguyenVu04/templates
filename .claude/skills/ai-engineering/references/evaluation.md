# LLM Evaluation

Without evals, every prompt edit is a gamble and every model upgrade is a leap of faith. The goal is a cheap, trusted harness that answers "did this change make things better?" in minutes. Evals are to LLM apps what tests are to code — build them alongside the feature, not after.

## The eval dataset

- Start small and real: **20–50 cases beats zero**; grow to 100–300. Sources in priority order: real production inputs (sampled + labeled), failure cases from bug reports (every production failure becomes an eval case — the regression-test discipline), synthetic cases for coverage of edge conditions (LLM-generate, human-filter).
- Each case: input, expected output or grading criteria, and tags (category, difficulty, edge-case type). Tags enable slice analysis — aggregate scores hide category regressions.
- Include: happy path, edge cases (empty, huge, malformed, mixed-language), adversarial (injection attempts, off-topic, unanswerable — expected behavior: refuse/say-unknown), and cases where the correct answer is "I don't know."
- Version the dataset like code. When the product changes, review cases for staleness.
- Hold out a slice you rarely run, to detect overfitting your prompts to the eval set itself.

## Choosing graders (cheapest that measures what matters)

1. **Code assertions** — exact match, contains/regex, valid JSON, schema-conforms, length bounds, latency/cost budgets, citation format present. Free, deterministic, run always. A surprising fraction of quality is checkable this way.
2. **Semantic similarity** — embedding cosine vs reference for paraphrase-tolerant matching. Rough but useful for triage.
3. **LLM-as-judge** — for subjective/qualitative criteria (helpfulness, faithfulness, tone). Powerful but must be designed and calibrated (below).
4. **Human review** — gold standard; spend it calibrating judges and auditing samples, not grading everything.

Task-specific canonical metrics: extraction → per-field precision/recall vs gold; classification → accuracy/F1 (it's just ML eval); RAG → retrieval hit-rate@k + faithfulness + answer correctness (stage-separated, see [rag.md](rag.md)); agents → task success rate + steps + cost; summarization → faithfulness (no invented facts) + coverage of key points (judge with rubric).

## LLM-as-judge that can be trusted

Design rules:
- **Binary or 3-level judgments per criterion**, not 1–10 scores (models can't calibrate fine scales; humans can't either). Decompose "quality" into separate judged criteria: faithful? complete? concise? correct-format?
- Give the judge a **rubric with examples** of pass and fail, and require reasoning-then-verdict, output as structured JSON.
- Use a strong model as judge; judge model ≠ judged model where feasible (self-preference bias).
- Known biases to design around: position bias in pairwise comparisons (randomize A/B order, run both orders), length bias (state explicitly that longer ≠ better), style-over-substance (rubric anchors on factual criteria).
- **Calibrate before trusting**: human-label 30–50 cases, measure judge-human agreement (aim ≳ 85–90% on binary). Below that, fix the rubric, not the threshold. Re-calibrate when the judge model changes.
- Pairwise (A vs B) is more sensitive for comparing two variants; absolute grading scales better across many runs. Use pairwise for decisions, absolute for dashboards.

## The harness

Requirements: run the full set from CLI/CI in minutes; parallel API calls; **run each case n≥3 times** if temperature > 0 (report mean and variance — single runs of stochastic systems are noise); cache (input, prompt-version, model) → output to avoid re-paying for unchanged cells; output per-case results + per-tag rollups + diff vs baseline run.

```
results/
  run_2026-07-07_promptv12/
    config.json      # prompt version, model, params, dataset version
    cases.jsonl      # per-case: input, output, grades, latency, tokens
    summary.json     # per-tag pass rates, cost, deltas vs baseline
```

Pytest-style assertions work for the code-graded layer; promptfoo/braintrust/langsmith or a ~200-line custom script for the rest. A custom script you understand beats a framework you fight.

## Workflow discipline

- **Change one variable per run** (prompt XOR model XOR params) and diff against the baseline. Look at per-tag deltas and read the actual diffs of regressed cases — aggregate scores lie by omission.
- Gate merges: prompt/model changes run the eval suite in CI; regression on protected tags blocks.
- Model upgrades are eval events, not drop-in swaps — full suite, read regressions, re-tune prompts.
- Track the metric ceiling: when pass rate saturates ≳95%, the eval set is too easy — add harder cases (eval sets are living).

## Online evaluation

- Log (input, prompt version, output, latency, cost) for all production traffic; sample for human/judge review.
- Implicit signals: user retry/rephrase rate, thumbs, copy-rate, task abandonment, escalation-to-human rate — define per product.
- A/B test prompt/model variants on live traffic with the same statistical discipline as any experiment (randomize by user, fixed horizon or sequential test — see the `machine-learning` skill, `references/statistics.md`).
- Drift watch: input distribution shifts (new topics, new languages) make the offline eval set stale; periodically fold fresh production samples in.
