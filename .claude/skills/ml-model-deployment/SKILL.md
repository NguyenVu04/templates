---
name: ml-model-deployment
description: Evaluate, export, and deploy trained ML/PyTorch models to production — choosing the right metrics, exporting to TorchScript/ONNX, serving with FastAPI, containerizing with Docker, optimizing inference (quantization, batching), and monitoring for drift. Use this skill whenever the user wants to serve a model behind an API, "triển khai model", "deploy", build an inference endpoint, convert a model for production, speed up inference / reduce model size, or set up model versioning and monitoring. Also trigger when the user asks how to properly evaluate a final model or report metrics before release.
---

# ML Model Evaluation & Deployment

A model is done when it's reproducibly evaluated, exported to a stable artifact, served behind a versioned API, and monitored. This skill covers that path end-to-end.

## 1. Final evaluation (gate before deployment)

- Evaluate on the **held-out test set exactly once**, using the checkpoint selected by validation. Re-running test after changes turns test into a second validation set.
- Report metrics that match the product decision, not just what's easy:
  - Classification: accuracy is insufficient under imbalance — report precision/recall/F1 per class, PR-AUC, confusion matrix; pick the operating threshold on validation for the business constraint (e.g., recall ≥ 0.95).
  - Regression/localization: MAE/RMSE plus **error percentiles** (median, P90, P95) and a CDF plot — means hide tail behavior users actually feel.
  - Uncertainty: mean ± std across seeds; bootstrap CIs on the test set for headline numbers.
- **Slice the evaluation**: metrics per segment (per class, per region/cell, per device type, per time period). Aggregate numbers hide segment failures — a model can look fine overall and be unusable for one important slice.
- Freeze and version together: weights + preprocessing artifacts + config + metrics report. The preprocessing (scaler, encoder, vocabulary) is part of the model; version them as one bundle.

## 2. Export

Decide the target first:

| Target | Format | Notes |
|---|---|---|
| Python server (FastAPI) | plain PyTorch `state_dict` or TorchScript | simplest; fine for most services |
| Cross-language / edge / max perf | **ONNX** → ONNX Runtime / TensorRT | broadest compatibility |
| Mobile | ONNX → CoreML/TFLite, or ExecuTorch | |

```python
# state_dict (always save this regardless of other exports)
torch.save({"model": model.state_dict(), "config": asdict(cfg)}, "model_v1.pt")

# ONNX
model.eval()
torch.onnx.export(model, dummy_input, "model_v1.onnx",
                  input_names=["x"], output_names=["y"],
                  dynamic_axes={"x": {0: "batch"}, "y": {0: "batch"}},
                  opset_version=17)
```

**Always verify export parity**: run the same inputs through the original and exported model, `np.testing.assert_allclose(out_pt, out_onnx, rtol=1e-3, atol=1e-5)`. Silent numeric divergence after export is common (unsupported ops folded, different kernels).

Traps: export with `model.eval()`; data-dependent Python control flow in `forward` breaks tracing (use scripting or refactor); custom ops need opset support.

## 3. Serving with FastAPI

Structure: load model once at startup, validate inputs with Pydantic, keep preprocessing identical to training by loading the saved transformer artifact.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel, Field

state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    state["pre"] = joblib.load("artifacts/preprocessor.joblib")
    state["sess"] = ort.InferenceSession("artifacts/model_v1.onnx",
                                         providers=["CPUExecutionProvider"])
    yield
    state.clear()

app = FastAPI(lifespan=lifespan)

class PredictIn(BaseModel):
    features: list[float] = Field(..., min_length=N_FEATURES, max_length=N_FEATURES)

@app.post("/predict")
def predict(inp: PredictIn):
    x = state["pre"].transform([inp.features]).astype(np.float32)
    y = state["sess"].run(None, {"x": x})[0]
    return {"prediction": y.tolist(), "model_version": "v1"}

@app.get("/healthz")
def health(): return {"status": "ok"}
```

- PyTorch inference in an async endpoint blocks the event loop — use `def` (sync) endpoints so FastAPI runs them in the threadpool, or offload to `run_in_executor`.
- Wrap inference in `torch.inference_mode()` when serving raw PyTorch.
- Include `model_version` in every response; log request features + predictions (sampled) for later drift analysis.
- For GPU serving under load, add micro-batching (collect requests for a few ms, run one batch) — per-request GPU calls waste most of the device.

## 4. Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY artifacts/ artifacts/
COPY app/ app/
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- CPU-only inference: install the CPU torch wheel (`torch --index-url https://download.pytorch.org/whl/cpu`) or use ONNX Runtime only — saves ~2 GB of image.
- GPU: base on `nvidia/cuda:*-runtime` images + `--gpus all`; match CUDA versions between image and host driver.
- Pin everything (`uv.lock`); never `pip install torch` unpinned in a production image.
- Bake model artifacts into the image for immutability, or mount/download versioned artifacts at startup for faster model-only updates — choose one and be explicit.

## 5. Inference optimization (apply only if latency/size requires)

In order of effort-to-payoff:
1. Batch requests; right-size `num_threads` for CPU (`torch.set_num_threads`).
2. ONNX Runtime / `torch.compile` — often 1.5–3× free speedup.
3. **Dynamic quantization** (int8 weights, `torch.ao.quantization.quantize_dynamic` or ONNX quantization) — ~4× smaller, big CPU speedup, minimal accuracy loss for Linear-heavy models. Always re-run the evaluation suite after quantizing.
4. Distillation / pruning — only when the above isn't enough; costs retraining.

Measure with realistic payloads: report P50/P95/P99 latency and throughput under concurrency (e.g., `locust`/`k6`), not single-request timings.

## 6. Monitoring & lifecycle

- **Operational**: latency percentiles, error rate, throughput, GPU/CPU memory — standard service monitoring (Prometheus/Grafana).
- **Data drift**: compare live feature distributions to the training distribution (PSI or KS test per feature, weekly). Drift precedes metric decay and is detectable without labels.
- **Model performance**: when ground truth arrives later, join predictions with outcomes and track the real metric over time; alert on degradation beyond the validation confidence interval.
- Keep a rollback path: previous model version deployable in one step; canary or shadow-deploy new versions (serve both, compare outputs) before full cutover.
- Retraining is a pipeline, not an event: fixed data → train → eval-gate → export → deploy steps, so every release is reproducible.
