# PyTorch Training & Debugging

Training code fails silently more often than it crashes. This reference provides a reference training loop, a debugging decision tree, and non-negotiable hygiene (reproducibility, checkpointing, tracking).

## Reference training loop

```python
def train(model, loaders, cfg):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.wd)
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=cfg.lr, total_steps=cfg.epochs * len(loaders["train"]))
    scaler = torch.amp.GradScaler("cuda")
    best_val, patience = float("inf"), 0

    for epoch in range(cfg.epochs):
        model.train()
        for batch in loaders["train"]:
            x, y = (t.to(device, non_blocking=True) for t in batch)
            opt.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.float16):
                loss = criterion(model(x), y)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.clip)
            scaler.step(opt); scaler.update(); sched.step()

        val_loss = evaluate(model, loaders["val"], device)   # model.eval() + no_grad inside
        log({"epoch": epoch, "val_loss": val_loss, "lr": sched.get_last_lr()[0]})
        if val_loss < best_val:
            best_val, patience = val_loss, 0
            save_checkpoint(model, opt, sched, epoch, cfg, "best.pt")
        elif (patience := patience + 1) >= cfg.early_stop:
            break
```

Baseline defaults: AdamW, lr=3e-4 (1e-5..5e-5 when fine-tuning pretrained), weight_decay=0.01, grad clip 1.0, OneCycle or cosine-with-warmup schedule. Change one thing at a time from these.

Non-negotiables baked in above:
- `model.train()` / `model.eval()` toggled correctly (dropout & BatchNorm behave differently).
- `torch.no_grad()` (or `torch.inference_mode()`) in evaluation.
- Checkpoint = model + optimizer + scheduler + epoch + config + metric, not just weights.
- Select the checkpoint by **validation** metric; report **test** exactly once, at the end.

## Before real training: the overfit test

Take 1–2 batches (~32–64 samples), train several hundred steps. Loss must go to ~0 / accuracy to ~100%. If it can't, there is a bug — no point launching a full run. This single test catches: wrong loss/target pairing, shape broadcasting bugs (`(B,1)` vs `(B,)` silently broadcasting in MSE), frozen parameters, data/label misalignment, forgotten `zero_grad`.

## Debugging decision tree

**Loss = NaN/inf**
1. Check input data: `assert torch.isfinite(x).all()` — usually a NaN in data or an unclipped sentinel value.
2. Lower LR by 10×; add/verify grad clipping.
3. Look for `log(0)`, `sqrt(0)`, division by zero in custom losses — add `eps=1e-8`.
4. FP16 overflow with autocast: check `scaler` is actually used; try `bfloat16` (no scaler needed) if hardware supports it.
5. Locate the step: `torch.autograd.set_detect_anomaly(True)` (slow — debug only).

**Loss flat / not decreasing**
1. Run the overfit test above; if it fails, it's a bug, not a tuning problem.
2. LR too low or too high (oscillating): sweep {1e-2, 1e-3, 3e-4, 1e-4} for a few hundred steps each.
3. Verify gradients flow: `[(n, p.grad.norm().item()) for n, p in model.named_parameters() if p.grad is not None]` — all-zero or missing grads mean a detached graph (`.detach()`, `.item()`, numpy round-trip, or an `argmax` inside the forward path).
4. Check data isn't shuffled against labels, and normalization is applied consistently.

**Train ↓ but val ↑ (overfitting)**: more augmentation → stronger weight decay/dropout → smaller model → more data. In that order.

**Val "too good"**: suspect leakage — grouped entities split randomly, transform fitted on full data, target leakage in a feature. Fix the split before believing any number (see [data.md](data.md)).

**Train and val both good, test/production bad**: distribution shift. Compare feature distributions train-vs-test; consider domain adaptation. Monitor domain classifier accuracy ≈ 0.5 as a health signal that domains are aligned when using adversarial DA.

**CUDA OOM**: reduce batch size + gradient accumulation → AMP → activation checkpointing → smaller model. Also check for the classic leak: accumulating `loss` (with graph) instead of `loss.item()` in a running total.

**Too slow**: profile first (`torch.profiler` or just time data-loading vs compute). If GPU util is low, the bottleneck is the DataLoader (`num_workers`, `pin_memory`, precompute transforms). Then: AMP, `torch.compile(model)`, larger batch, SDPA attention.

## Reproducibility

```python
def set_seed(seed=42):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
seed everything, and for strict determinism:
torch.use_deterministic_algorithms(True)   # may need CUBLAS_WORKSPACE_CONFIG=:4096:8
g = torch.Generator(); g.manual_seed(seed)  # pass to DataLoader(shuffle=True, generator=g)
```

Log the seed with every run. For papers/theses, report mean ± std over ≥3 seeds — single-seed comparisons of nearby configs are noise.

## Experiment tracking

Every run must record: config (all hyperparams), git commit / code version, dataset version + split hash, seed, environment (`torch.__version__`, GPU), and per-epoch metrics.

- Default to **MLflow** for local/self-hosted (`mlflow.log_params(asdict(cfg))`, `mlflow.log_metrics(...)`, `mlflow.log_artifact("best.pt")`); W&B when cloud dashboards/collaboration are wanted; TensorBoard for quick local curves.
- Log the config as a YAML/JSON artifact so any run is re-launchable from its logged config alone.
- Name runs meaningfully (`dann_lambda0.3_seed42`), not timestamps.
- Log per-term losses in multi-loss setups (task vs auxiliary) — a single aggregate loss hides which term is misbehaving.

## Hyperparameter tuning order

Tune in decreasing order of impact and stop when improvements are within seed noise:
1. Learning rate (log-scale sweep)
2. Model capacity (width/depth)
3. Regularization (weight decay, dropout, augmentation strength)
4. Batch size / schedule shape
5. Everything else (Optuna with pruning if a systematic search is warranted; ~20–50 trials on the 2–4 params that matter)
