# Model Fine-tuning

Fine-tuning is the last resort that people reach for first. It changes model *behavior* (style, format, task-specific skill); it is bad at adding *knowledge* (facts belong in RAG). Decide honestly before burning GPU-hours, and remember: data quality decides the outcome more than any hyperparameter.

## Fine-tune vs prompt vs RAG

Try in this order — each step is 10× cheaper than the next:
1. **Better prompting** (few-shot examples, clearer instructions) — solves most "the model doesn't do X" complaints.
2. **RAG** — when the problem is missing/changing knowledge (see [rag.md](rag.md)).
3. **Fine-tune** — when: the format/style must be deeply consistent, few-shot examples eat too much context at scale, the task is genuinely unusual (domain jargon, structured transformations), latency/cost demands a small specialized model replacing a big prompted one, or prompting has plateaued with an eval to prove it.

Have an eval set BEFORE fine-tuning (see [evaluation.md](evaluation.md)) — otherwise "it worked" is vibes. Baseline the prompted big model and the prompted base model on it; the fine-tune must beat what you'd get for free.

## Dataset preparation (where success is decided)

- **Quality >> quantity**: 500–2,000 excellent examples beat 50k scraped ones for task adaptation. Every training example teaches the model "output exactly this given this" — mediocre examples train mediocrity in.
- Format = the model's chat template. Use `tokenizer.apply_chat_template` — hand-rolled templates with wrong special tokens are the #1 silent fine-tuning killer (trains fine, generates garbage).
- Match training distribution to inference reality: same system prompt style, same input formats, same length profile. Include edge cases and refusal/"I don't know" examples if the deployed model needs them.
- Cleaning pass: dedupe (exact + near-dup), strip PII if required, verify labels/outputs manually on a random 50 — you will find errors.
- **Decontaminate against your eval set** (exact and near-match) — leaking eval into training data invalidates everything downstream.
- Splits: hold out val (for early stopping) and test (untouched) with the same grouping discipline as any ML project.
- Synthetic data (strong model generates examples) bootstraps well: generate → human/judge filter aggressively (keep the best 30–50%) → check diversity (dedupe near-identical generations). Mind the model's license terms for distillation.

## LoRA / QLoRA

Full fine-tuning is rarely necessary; LoRA gets ~equivalent task performance at a fraction of memory:

```python
from peft import LoraConfig, get_peft_model
cfg = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05,
    target_modules=["q_proj","k_proj","v_proj","o_proj",
                    "gate_proj","up_proj","down_proj"],   # attn + MLP: better than attn-only
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, cfg)   # print trainable %: expect ~0.5–2%
```

- r=8–16 default; r=32–64 for harder/larger behavioral changes; alpha ≈ 2r. Diminishing returns above — more data beats more rank.
- **QLoRA** (base in NF4 4-bit + LoRA in bf16, `bits_and_bytes` + `prepare_model_for_kbit_training`): fine-tune 7–8B on a single 24GB GPU, ~3B on 12GB. Small quality cost vs LoRA, huge accessibility win.
- Memory levers (same as any training): gradient checkpointing, gradient accumulation, bf16, `paged_adamw_8bit`, FlashAttention/SDPA, shorter `max_seq_len` (biggest single lever — pack short examples to fill sequences).

## Training (SFT)

Use TRL's `SFTTrainer` (or axolotl/LLaMA-Factory configs) rather than hand-rolling:
- Hyperparameter starting points: LR **1e-4–2e-4 for LoRA** (10× lower, ~1e-5–2e-5, for full FT), cosine schedule + 3–5% warmup, **1–3 epochs** (more overfits fast on small sets), effective batch 16–64 via accumulation, weight decay 0.
- **Mask the loss to completion tokens only** (train on assistant responses, not the prompt) — TRL's completion-only collator / `assistant_only_loss`. Training on prompts wastes capacity and teaches prompt-parroting.
- Watch val loss per epoch — but val loss ≠ task quality; run the real eval on checkpoints. Generation degeneration (repetition, format collapse) can appear while loss still improves.
- Overfit signals: val loss up while train down; outputs memorize training phrasings verbatim. Fix: fewer epochs, more/varied data, lower r or LR.
- **Catastrophic forgetting** (model gets your task, loses general ability): lower LR, fewer epochs, and mix 5–10% general instruction data into training; always eval general capability, not just your task.

## Preference tuning (DPO)

When SFT gets the format right but outputs need to be *better* along some axis (helpfulness, safety, style preference): build (prompt, chosen, rejected) pairs — from human rankings, judge-ranked generations of your SFT model, or best-vs-worst of n samples — then TRL `DPOTrainer` on top of the SFT checkpoint (beta≈0.1, LR ~5e-6, LoRA fine). DPO amplifies preference-pair quality (and its biases) — audit pairs like training data, because they are. SFT first, always; DPO refines, it doesn't teach the task.

## Evaluation & shipping

- Compare on your eval suite: fine-tuned vs base-prompted vs big-model-prompted, plus a general-capability check (a few MMLU-style or held-out instruction tasks) for forgetting, plus safety/refusal behavior if user-facing.
- Read generations, not just scores — 30 side-by-side samples reveal failure modes metrics miss (subtle format drift, tone shifts, new hallucination patterns).
- Ship: merge LoRA into base (`merge_and_unload`) for single-adapter serving → quantize (AWQ/GGUF) → **re-run the eval on the quantized artifact** → serve (see [serving.md](serving.md); multi-adapter setups serve adapters unmerged).
- Version the triple (base model, adapter, dataset version) together; a fine-tune without its data lineage cannot be debugged, improved, or trusted.
