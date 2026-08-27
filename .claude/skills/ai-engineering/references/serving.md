# LLM Inference Serving

Serving LLMs is a memory-bandwidth problem wearing a compute costume. Two numbers rule everything: how much VRAM the weights + KV cache need, and how many tokens/second the memory bus can feed. Estimate before downloading anything.

## VRAM math (do this first)

```
Weights:  params × bytes/param   (FP16=2, INT8=1, INT4≈0.55 incl. overhead)
KV cache: 2 × layers × kv_heads × head_dim × bytes × seq_len × batch
          (GQA models have kv_heads << attention heads — check config.json)
Total ≈ weights + KV + ~10–20% overhead (activations, CUDA context)
```

Quick reference (weights only): 7–8B ≈ 15GB FP16 / 8GB INT8 / 4.5GB INT4; 14B ≈ 28/14/8; 32B ≈ 64/32/18; 70B ≈ 140/70/38. KV cache is NOT small: long contexts × big batches can exceed weight memory — it's why "the model loads but OOMs under load."

Rule of thumb for a GPU with X GB: comfortable ≈ INT4 model of ~1.6×X billion params with modest context. A 4GB GPU → 3–4B INT4 models (or CPU-offload with llama.cpp, slowly); 24GB → 32B INT4 or 8B FP16 with real batch sizes.

## Engine selection

| Situation | Engine |
|---|---|
| Production GPU serving, concurrency | **vLLM** (PagedAttention, continuous batching, OpenAI-compatible API) — default |
| HF ecosystem / enterprise support | TGI |
| CPU / Apple Silicon / small GPU / edge | **llama.cpp** (GGUF, CPU+GPU layer offload via `-ngl`) |
| Local dev convenience | Ollama (llama.cpp wrapper; fine for dev, thin for prod ops) |
| Max NVIDIA performance, effort OK | TensorRT-LLM |

```bash
# vLLM: OpenAI-compatible server in one line
vllm serve Qwen/Qwen2.5-7B-Instruct-AWQ \
  --max-model-len 8192 --gpu-memory-utilization 0.90
```
Point any OpenAI SDK at `http://host:8000/v1` — keeping the OpenAI-compatible interface makes cloud↔local swaps a config change.

## Quantization

- **Weight-only 4-bit (AWQ or GPTQ for GPU serving; GGUF Q4_K_M for llama.cpp)** is the sweet spot: ~4× memory cut, minor quality loss on 7B+, often FASTER than FP16 (memory-bound decoding loves smaller weights).
- Prefer pre-quantized checkpoints from the model publisher or reputable quantizers on HF; quantize yourself only when serving a custom fine-tune.
- Quality degrades more on small models (≤3B) and on tasks needing precision (math, code) — **always run your eval suite (see [evaluation.md](evaluation.md)) on the quantized model**, not the paper's benchmarks.
- KV cache quantization (FP8/INT8 KV) buys longer contexts or bigger batches when weights already fit.
- bitsandbytes 4/8-bit is for experimentation/fine-tuning convenience, not serving throughput.

## Throughput & latency mechanics

Know the two phases: **prefill** (prompt processing — compute-bound, parallel) and **decode** (token-by-token — memory-bandwidth-bound). Metrics that matter: TTFT (time to first token, dominated by prefill/queueing), ITL/TPOT (inter-token latency), and total throughput (tokens/s across all requests).

- **Continuous batching** (vLLM/TGI default) is the big win: requests join/leave the batch per-step; GPU stays fed. Single-request serving wastes ~90% of the hardware.
- Batch size ↑ → throughput ↑, per-request latency ↑ mildly, until KV memory runs out. Tune `--max-num-seqs` / `--max-model-len` against your VRAM budget; vLLM logs preemptions when KV thrashes — that's the signal you overcommitted.
- **Prefix caching** (`--enable-prefix-caching`): shared system prompts / few-shot prefixes across requests are computed once — massive TTFT win for chat apps with long system prompts.
- Speculative decoding / Medusa-style: 1.5–2.5× decode speedup when a good draft model exists; evaluate acceptance rate on your traffic.
- Long contexts: prefill cost grows ~quadratically; chunked prefill (vLLM flag) keeps decode latency stable while long prompts process.

## LoRA adapter serving

Serve one base model + many adapters instead of N full copies:
```bash
vllm serve <base> --enable-lora --lora-modules customer_a=/path/a customer_b=/path/b
# request with model="customer_a"
```
Adapters are tiny (MBs) and hot-swappable; ideal for per-tenant/per-task fine-tunes. Merge adapter into base weights only when serving exactly one adapter and want zero overhead (then quantize the merged model).

## Operations

- Container: match CUDA versions (image ↔ host driver); pin engine version; models mounted or pulled by digest — never "latest".
- Health/readiness probes must do a real tiny generation (model loaded ≠ model working); load models at startup, fail fast.
- Observe: TTFT/ITL percentiles, queue depth, KV cache utilization, preemption count, GPU memory/util (dcgm/nvidia-smi exporters), tokens/s. Alert on queue growth — it precedes timeout storms.
- Capacity: load-test with realistic prompt/output length distributions (`vllm bench serve` or k6 + streaming) — synthetic short prompts overestimate capacity badly.
- Multi-GPU: tensor parallel (`--tensor-parallel-size N`) to fit big models; prefer fewer larger GPUs over many small ones (interconnect overhead); pipeline parallel only when TP can't fit it.
- Cheap first question for any deployment: would an API endpoint be cheaper? Self-hosting wins at sustained high volume, hard data-residency requirements, or custom fine-tunes — not for a demo used twice a day.
