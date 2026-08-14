---
name: llm-application-engineering
description: Build production applications on top of LLM APIs — prompt engineering, structured output (JSON/function calling), streaming, retries and fallbacks, context window management, caching, and cost control. Use this skill whenever the user is integrating an LLM API (Anthropic/OpenAI/local) into an application, writing or improving prompts programmatically, parsing model output into typed data, handling API errors and rate limits, reducing token costs or latency, or building features like summarization, extraction, classification, or chat on top of a model ("gọi API LLM", "prompt engineering", "structured output", chatbot backend).
---

# LLM Application Engineering

An LLM app is a normal distributed system with a probabilistic component in the middle. Engineer around three facts: outputs vary, tokens cost money, and the API will fail. Treat prompts as code (versioned, tested, reviewed) and never trust output shape without validation.

## Prompt engineering that actually moves quality

In rough order of impact:
1. **Show, don't tell — few-shot examples.** 2–5 diverse input→output examples outperform paragraphs of instructions. Include an edge case and a "reject/null" example.
2. **Structure the prompt** with clear sections (XML tags work well): role/task, rules, examples, then the actual input LAST (recency matters).
3. **Give the model an out**: "if the answer is not in the document, return `null`" — the single best hallucination reducer in extraction tasks.
4. **Positive instructions** ("respond in formal English") beat negative ones ("don't be casual"); constraints beat vibes ("≤3 sentences" beats "be brief").
5. **Ask for reasoning before the answer** for hard tasks (or use a reasoning-enabled model); ask for the answer only, for easy high-volume tasks (cost).
6. Keep a **prompt registry**: prompts in version control as templates with named variables, changelog, and eval scores per version (see `llm-evaluation` skill). Never edit prompts live in production code strings.

Debug prompts empirically: collect failing cases, change ONE thing, rerun the eval set. Prompt work without an eval set is astrology.

## Structured output

Never parse free text with regex hope. In order of preference:
1. **Native structured output / function-calling** with a JSON schema — the API constrains generation.
2. Ask for JSON + validate with Pydantic + **one retry with the error message**:

```python
class Extraction(BaseModel):
    company: str
    amount_usd: float | None
    confidence: Literal["high", "medium", "low"]

def extract(text: str, attempt: int = 0) -> Extraction:
    raw = call_llm(PROMPT.format(input=text))
    raw = strip_code_fences(raw)
    try:
        return Extraction.model_validate_json(raw)
    except ValidationError as e:
        if attempt >= 1: raise
        return extract(text + f"\n\nPrevious output was invalid: {e}. Return only valid JSON.",
                       attempt + 1)
```

Schema design for LLMs: flat beats deeply nested; enums/Literals beat free strings; add a `confidence` or `evidence` field when downstream logic branches on trustworthiness; field descriptions in the schema are prompt real estate — use them.

## Reliability

- **Retries with exponential backoff + jitter** on 429/5xx/timeouts (use `tenacity`). Set explicit timeouts — default SDK timeouts are often too long for user-facing paths.
- **Fallback chain**: primary model → cheaper/other-provider model → graceful degradation (cached answer, "try again later"). Wrap providers behind one interface so fallback is config, not code surgery.
- **Idempotency**: LLM calls that trigger side effects (send email, write DB) need idempotency keys — retries must not double-execute actions.
- **Non-determinism**: even temperature=0 isn't bit-stable across API versions. Any "it changed behavior" investigation starts with: did the model/version change?
- Log every call: prompt version, model, input hash, output, latency, token counts. You cannot debug or evaluate what you didn't log (redact PII per policy).

## Context window management

- Budget explicitly: system + few-shot + retrieved context + history + output headroom. Count with the provider's tokenizer, don't estimate by characters.
- Long chat history: keep system prompt + recent K turns verbatim + an LLM-written running summary of older turns. Summarize asynchronously, not on the hot path.
- Long documents: don't stuff — retrieve relevant parts (see `rag-pipeline` skill) or map-reduce (summarize chunks → summarize summaries).
- Models attend best to the start and end of context — put instructions at the start, the question/input at the end, bulk context in the middle.

## Cost & latency

- **Model tiering** is the biggest lever: route easy/high-volume tasks (classification, routing, simple extraction) to small cheap models; reserve the big model for hard steps. A router prompt on a cheap model deciding the tier often pays for itself immediately.
- **Prompt caching**: structure prompts so the long static prefix (system, examples, docs) is identical across calls and only the suffix varies — cached prefix tokens cost a fraction of the price and cut latency.
- **Streaming** for anything user-facing: perceived latency = time-to-first-token. Stream, render progressively, validate the full output at the end.
- Batch APIs for offline bulk work (typically ~50% cheaper).
- Track cost per feature: tokens_in/out × price, tagged by prompt version and feature. Cost regressions ship silently with prompt edits.
- Output tokens dominate latency; cap `max_tokens` realistically and instruct brevity where possible.

## Security basics

- Treat all user input and all retrieved/tool content as untrusted: prompt injection is the #1 attack. Mitigations: separate system vs user roles properly, delimit untrusted content clearly, never let raw model output execute privileged actions without validation/allow-lists, and constrain tools with least privilege (see `agent-development` skill).
- Never interpolate secrets into prompts; assume prompts leak (users can often extract them).
- Validate model output before it touches: SQL, shell, URLs to fetch, HTML to render (XSS via markdown), or any state-changing API.
