---
paths:
  - "**/prompts/**"
  - "**/*prompt*.py"
  - "**/evals/**"
  - "**/*.j2"
  - "**/*.jinja"
---

# LLM application code

Read `ai-engineering/SKILL.md` before changing prompts or model-calling code. These are the
operational rules for the files this repository treats as prompt and eval assets.

## Prompts are code

- Prompts live in version control as templates with named variables, a changelog, and an eval
  score per version. Never edit a prompt as an inline string literal in production code.
- Changing a prompt without re-running the eval set is not a change, it is a gamble. Change one
  variable per run — prompt XOR model XOR params — and diff against the baseline.
- Keep the prompt version in every log line, so a behavior change can be traced to a diff.

## Output handling

- Native structured output / function calling with a schema first. Otherwise: validate with
  Pydantic and retry **once**, feeding the validation error back into the prompt. Never
  regex-parse free text and hope.
- Flat schemas beat nested; `Literal`/enums beat free strings; field descriptions are prompt
  real estate.
- Give the model an out (`return null` when the answer is not in the document). It is the single
  best hallucination reducer in extraction.

## Reliability and cost

- Retries with exponential backoff + jitter on 429/5xx/timeouts, with explicit timeouts set —
  SDK defaults are too long for user-facing paths.
- Any LLM call that triggers a side effect needs an idempotency key. Retries must not
  double-execute.
- Count tokens with the provider's tokenizer, never by character estimate.

## Security

- **All user input, retrieved context and tool output is untrusted.** Delimit it as data, state
  that tool content is never instructions, and gate consequential actions behind allow-lists and
  confirmations enforced in code — so an injected instruction cannot cause damage even if the
  model follows it.
- API keys are read from the environment. Never inline, never logged, never committed.
- Log prompt version, model, latency and token counts; redact PII per policy before it reaches
  a log sink.
