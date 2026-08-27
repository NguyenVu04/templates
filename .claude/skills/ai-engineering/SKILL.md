---
name: ai-engineering
description: >-
  Everything built on top of LLMs — prompt engineering and structured output, RAG over your own
  documents, agents that use tools, evaluation harnesses, fine-tuning (LoRA/QLoRA/DPO), and
  self-hosted inference serving. This SKILL.md is the router: identify the phase, then read ONLY
  the relevant reference file before writing code.
when_to_use: >-
  Use whenever the user integrates an LLM API or writes/improves a prompt programmatically
  ("gọi API LLM", "prompt engineering", "structured output", chatbot backend, summarization,
  extraction, classification); parses model output into typed data; builds Q&A over their own
  documents ("RAG", "vector search", "semantic search", "embedding", "chatbot đọc tài liệu",
  "hỏi đáp trên tài liệu nội bộ", retrieves wrong passages); wants an LLM to take actions
  ("agent", "function calling", "tool use", "MCP", "workflow tự động", agent loops forever or
  picks wrong tools); asks whether a prompt/RAG/agent is any good ("eval", "đánh giá chất lượng
  LLM", "LLM-as-judge", comparing prompts or models, vibe-checking); adapts an open-weight model
  ("fine-tune", "LoRA", "QLoRA", "huấn luyện lại model", "train model trên dữ liệu riêng",
  fine-tune vs prompt vs RAG, model forgot how to follow instructions); or runs models on their
  own hardware ("vLLM", "quantization", "AWQ", "GGUF", "chạy model local", "deploy LLM",
  "GPU nào đủ", "out of memory khi load model").
---

# AI Engineering (LLM · RAG · Agents)

A complete playbook for building on top of language models, from a first API call to a
self-hosted, evaluated, fine-tuned system. This SKILL.md is the router: classify the task, then
read only the reference files it points at. They are short.

## Phase routing table

| The user wants to... | Read |
|---|---|
| Call an LLM API, write/version prompts, get structured output, handle retries, cost, latency, context windows | `references/applications.md` |
| Answer questions over their own documents — chunking, embeddings, vector stores, hybrid search, reranking | `references/rag.md` |
| Let the model take actions — tool/function design, agentic loops, state and memory, guardrails, MCP | `references/agents.md` |
| Measure whether any of it works — eval datasets, graders, LLM-as-judge, regression tests in CI | `references/evaluation.md` |
| Adapt a model to their task — dataset prep, chat templates, LoRA/QLoRA, SFT, DPO | `references/finetuning.md` |
| Run open-weight models on their own hardware — VRAM math, engines, quantization, throughput, LoRA serving | `references/serving.md` |

Most real tasks span phases. "Build a chatbot over our internal docs" is `rag.md` +
`applications.md` + `evaluation.md`. "Our agent picks the wrong tool" is `agents.md` +
`evaluation.md`. Read all the relevant files.

## The escalation ladders

Two ordered ladders govern every decision in this skill. Climb only as far as the problem
actually requires — each rung costs roughly 10× the one below it.

**Capability ladder — how to make the model do X:**
1. **Better prompting** — few-shot examples, clearer instructions, giving the model an out. Solves
   most "the model doesn't do X" complaints.
2. **RAG** — when the problem is missing or changing *knowledge*. Facts belong in retrieval.
3. **Fine-tuning** — when the problem is *behavior*: format/style consistency, few-shot examples
   eating context at scale, a genuinely unusual task, or a small specialized model replacing a
   big prompted one. Never for adding knowledge.

**Autonomy ladder — how much the model gets to decide:**
1. **Chain** (fixed steps, LLM fills content) — most "agent" ideas are actually this, and it is
   the most reliable.
2. **Router** (LLM picks one branch, code executes it).
3. **Agent loop** (LLM picks tools iteratively) — only when the path genuinely cannot be
   predetermined.

If you can draw the flowchart, build the flowchart. Agents are for when you can't.

## Non-negotiable defaults

These apply to every phase unless the user's existing codebase or explicit request says otherwise:

1. **An eval set exists before the change is judged.** Prompt work without an eval set is
   astrology; a fine-tune without one is vibes. 20–50 real cases beats zero — build it first,
   then change one variable per run. See `references/evaluation.md`.
2. **Prompts are versioned artifacts**, not inline string literals edited in place. Registry in
   version control, named variables, changelog, eval score per version.
3. **Never trust output shape.** Native structured output / function calling first; otherwise
   schema-validate (Pydantic) with exactly one repair retry carrying the error message.
4. **All retrieved and tool-returned content is untrusted input.** Web pages, emails, documents
   and tool results may contain instructions. Delimit them as data, and gate consequential
   actions behind allow-lists and confirmations enforced in *code*, so an injected instruction
   cannot cause damage even if the model follows it.
5. **Every call is logged** — prompt version, model, input hash, output, latency, token counts.
   You cannot debug or evaluate what you did not log. Redact PII per policy.
6. **Hard budgets on anything that loops** — max steps AND max tokens AND wall-clock timeout,
   with an explicit terminal state. "Silently stopped" is not a state.
7. **Model upgrades are eval events**, not drop-in swaps. Run the full suite, read the
   regressions, re-tune the prompts.

## Debugging order

When quality is bad, look in this order — it is roughly the order of probability:

1. **Retrieval, if RAG is involved.** Bad RAG answers are bad retrieval ~80% of the time. Inspect
   the retrieved chunks before touching the prompt or the model.
2. **The eval set.** If you cannot reproduce the failure as a case, you cannot fix it reliably.
3. **The prompt.** One change at a time, re-run the suite.
4. **The data** (for a fine-tune) — quality of examples decides the outcome more than any
   hyperparameter.
5. **The model.** Last, not first.

## Related skills

- `machine-learning` — classical ML and PyTorch. Use `references/statistics.md` for A/B
  significance on prompt variants, and `references/experimentation.md` for multi-seed discipline.
- `devops-engineering` — containers, Kubernetes, CI/CD and observability for anything you deploy.
- `fastapi-lifecycle` — serving an LLM feature behind a Python API.
