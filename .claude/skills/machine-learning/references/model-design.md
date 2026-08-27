# PyTorch Model Design

Good PyTorch models are boring: clean module boundaries, explicit shapes, standard building blocks, and a config-driven interface. Cleverness goes into the problem formulation, not the code.

## Architecture selection (before writing code)

Match architecture to data structure, and start smaller than feels right:

| Data | First choice | Escalate to |
|---|---|---|
| Tabular / fixed-length vectors | MLP (2–4 hidden layers) — but try LightGBM first as baseline | Wider/deeper MLP, FT-Transformer |
| Images | Pretrained ResNet/EfficientNet, fine-tuned | ViT if data is large |
| Sequences (text, time series) | Pretrained Transformer / 1D-CNN / GRU | Custom Transformer |
| Sets (unordered, variable-size) | DeepSets / Set Transformer (ISAB+PMA) | — |
| Multi-domain / sim-to-real | Base model + adaptation branch (DANN/CORAL/MMD) | — |

Rules of thumb: parameter count should be justified by dataset size (a 10M-param model on 40K samples will overfit without heavy regularization); prefer pretrained weights whenever the modality allows; a model that can't overfit a tiny subset is broken (see [training.md](training.md)).

## Module structure

One `nn.Module` per logical block; compose in a top-level model. Keep `forward` free of data-dependent Python branching where possible.

```python
class MLPBlock(nn.Module):
    def __init__(self, d_in: int, d_out: int, p_drop: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_in, d_out),
            nn.BatchNorm1d(d_out),      # LayerNorm for transformers / small batches
            nn.GELU(),
            nn.Dropout(p_drop),
        )
    def forward(self, x): return self.net(x)

class Model(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.encoder = ...
        self.head = ...
    def forward(self, x, mask=None):
        z = self.encoder(x, mask)
        return self.head(z)
```

Conventions that pay off:
- **Config dataclass** (`@dataclass ModelConfig`) holding all dims/hyperparams — never hardcode dims inside layers.
- **Document tensor shapes** in comments at each stage: `# (B, N, d_model)`. Shape bugs are the dominant PyTorch bug class.
- **Masks are first-class inputs**: for variable-length or partially-observed data, pass a boolean mask through the whole model; apply it inside attention (additive `-inf` on logits before softmax) and pooling (masked mean), never after.
- Multi-branch models (e.g., DANN = shared feature extractor + task head + domain head) should expose branches as attributes so training code can route losses and freeze parts independently.
- Return raw logits from the model; apply softmax/sigmoid only in loss (built into `CrossEntropyLoss`/`BCEWithLogitsLoss`) and at inference.

## Layer choice cheat sheet

- **Normalization**: BatchNorm for CNNs/MLPs with batch ≥ 32; LayerNorm for transformers, RNNs, small/variable batches, or anything with padding masks (BatchNorm statistics get polluted by padding).
- **Activation**: GELU or SiLU as default; ReLU fine for MLP baselines; never sigmoid/tanh in hidden layers of deep nets.
- **Dropout**: 0.1–0.3 typical; place after activation; disable via `model.eval()` at inference (a top-5 silent bug when forgotten).
- **Initialization**: PyTorch defaults are fine for standard layers. For custom layers, Kaiming for ReLU-family, Xavier for tanh/linear. Zero-init the final layer of residual branches for stability.
- **Attention**: use `nn.MultiheadAttention(batch_first=True)` or `F.scaled_dot_product_attention` (fused, fast) instead of hand-rolled attention unless the user is implementing a paper variant for learning purposes.

## Loss selection

| Task | Loss | Notes |
|---|---|---|
| Multi-class classification | `CrossEntropyLoss` | takes logits + int labels; `label_smoothing=0.1` often helps |
| Multi-label / binary | `BCEWithLogitsLoss` | `pos_weight` for imbalance |
| Regression, clean targets | `MSELoss` | |
| Regression with outliers | `HuberLoss(delta=…)` | tune delta to the scale where errors switch from "noise" to "outlier" |
| Imbalanced detection | Focal loss | or class-weighted CE first — simpler |
| Metric learning / retrieval | Triplet / InfoNCE | requires careful negative sampling |
| Distribution alignment (DA) | CORAL / MMD / adversarial (GRL) | auxiliary loss; weight with warm-up schedule |

Multiple losses: combine as `L = L_task + λ·L_aux` with λ warmed up from 0; log each term separately so you can see which one dominates.

## Dataset & DataLoader

```python
class MyDataset(Dataset):
    def __init__(self, X, y, transform=None): ...
    def __len__(self): ...
    def __getitem__(self, i):  # return tensors, apply transforms here
        ...

loader = DataLoader(ds, batch_size=cfg.bs, shuffle=True,
                    num_workers=4, pin_memory=True,
                    persistent_workers=True, drop_last=True)
```

- Do heavy preprocessing once offline (save to .npy/.pt/parquet); `__getitem__` should be cheap indexing plus light augmentation.
- Variable-length samples need a custom `collate_fn` producing padded tensors + masks.
- On Windows, guard entry with `if __name__ == "__main__":` when `num_workers > 0`.
- `drop_last=True` on train when using BatchNorm (a trailing batch of size 1 crashes it).

## Fitting into GPU memory

For constrained GPUs (e.g., 4 GB VRAM), apply in this order:
1. Mixed precision (`torch.autocast` + `GradScaler`) — near-free 40–50% memory cut.
2. Reduce batch size + **gradient accumulation** to keep effective batch constant.
3. `torch.utils.checkpoint` (activation checkpointing) on the largest blocks — trades ~30% compute for large memory savings.
4. Smaller `d_model`/depth; for attention, ISAB or flash/SDPA kernels instead of full O(N²).
5. Estimate before training: params × 4 bytes × ~4 (weights+grads+Adam states) + activations. A 25M-param model with Adam already needs ~400 MB before activations.

## Verify the skeleton before training

Always run these immediately after writing a model:

```python
model = Model(cfg)
print(sum(p.numel() for p in model.parameters() if p.requires_grad))  # param count
x = torch.randn(2, *input_shape)          # batch of 2, catches batch-dim bugs
out = model(x)
assert out.shape == (2, *expected_out)
loss = criterion(out, dummy_target); loss.backward()   # gradients flow end-to-end
```

Then hand off to the training pipeline (see [training.md](training.md)).
