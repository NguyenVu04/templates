"""UserPromptSubmit hook: route ML/LLM prompts to the right router skill.

Advisory only -- it never blocks. On a keyword match it emits `additionalContext`
naming the router skill to invoke and the reference file most likely to be needed.

The two tables below are the whole configuration; edit them without reading the
logic. Keys are the reference file, values are the trigger phrases.

Fails open: unparseable stdin or any unexpected exception exits 0 silently.

    echo '{"prompt":"RAG cua toi tra ve sai doan"}' | python skill_router.py
"""

import json
import re
import sys

AI_TRIGGERS = {
    "applications.md": [
        "prompt engineering", "structured output", "gọi api llm", "llm api", "few-shot",
        "few shot", "context window", "chatbot backend", "token cost", "prompt template",
        "anthropic api", "openai api", "streaming response",
    ],
    "rag.md": [
        "rag", "vector search", "semantic search", "vector database", "vector db", "embedding",
        "faiss", "qdrant", "pgvector", "chroma", "lancedb", "rerank", "bm25", "hybrid search",
        "chunking", "chunk size", "đọc tài liệu", "hỏi đáp trên tài liệu", "knowledge base",
    ],
    "agents.md": [
        "agentic", "agent loop", "function calling", "tool calling", "tool use", "mcp server",
        "react loop", "plan-execute", "workflow tự động", "tool schema", "guardrail",
    ],
    "evaluation.md": [
        "llm-as-judge", "llm as judge", "eval set", "eval suite", "eval dataset", "eval harness",
        "đánh giá chất lượng llm", "vibe check", "promptfoo", "braintrust", "langsmith",
        "regression test for prompt",
    ],
    "finetuning.md": [
        "fine-tune", "finetune", "fine tuning", "lora", "qlora", "peft", "dpo", "sft",
        "axolotl", "llama-factory", "huấn luyện lại model", "train model trên dữ liệu riêng",
        "chat template", "catastrophic forgetting",
    ],
    "serving.md": [
        "vllm", "llama.cpp", "ollama", "gguf", "awq", "gptq", "tensorrt", "kv cache",
        "continuous batching", "quantiz", "vram", "chạy model local", "deploy llm",
        "gpu nào đủ", "prefix caching", "tokens/s", "ttft",
    ],
}

ML_TRIGGERS = {
    "data.md": [
        "eda", "exploratory data", "phân tích dữ liệu", "data cleaning", "làm sạch dữ liệu",
        "feature engineering", "data leakage", "rò rỉ dữ liệu", "missing value", "imputation",
        "train_test_split", "train/test split", "class imbalance", "outlier", "groupkfold",
    ],
    "model-design.md": [
        "nn.module", "pytorch model", "kiến trúc mạng", "thiết kế mô hình", "xây dựng model",
        "dataloader", "loss function", "activation function", "batchnorm", "layernorm",
        "weight initialization", "multihead attention", "parameter count",
    ],
    "training.md": [
        "training loop", "huấn luyện model", "loss không giảm", "loss is nan", "nan loss",
        "overfitting", "cuda oom", "out of memory", "learning rate", "lr schedule",
        "early stopping", "mixed precision", "gradient accumulation", "mlflow", "tensorboard",
        "wandb", "torch.compile",
    ],
    "interpretability.md": [
        "shap", "feature importance", "permutation importance", "partial dependence",
        "giải thích model", "tại sao model dự đoán", "xai", "model audit", "error analysis",
        "fairness",
    ],
    "deployment.md": [
        "triển khai model", "onnx", "torchscript", "inference endpoint", "model serving",
        "model drift", "model registry", "serve the model", "export the model",
    ],
    "experimentation.md": [
        "ablation", "thí nghiệm", "luận văn", "so sánh phương pháp", "multi-seed",
        "reproducib", "fair baseline", "research experiment",
    ],
    "statistics.md": [
        "p-value", "p value", "statistically significant", "kiểm định", "so sánh hai nhóm",
        "a/b test", "ab test", "confidence interval", "effect size", "sample size",
        "t-test", "wilcoxon", "mann-whitney", "power analysis", "bonferroni",
    ],
}

ROUTERS = [("ai-engineering", AI_TRIGGERS), ("machine-learning", ML_TRIGGERS)]


def _pattern(phrase):
    """Word-bounded regex so 'rag' does not match 'storage'."""
    left = r"\b" if phrase[0].isalnum() else ""
    right = r"\b" if phrase[-1].isalnum() else ""
    return re.compile(left + re.escape(phrase) + right, re.IGNORECASE)


PATTERNS = {
    router: {ref: [_pattern(p) for p in phrases] for ref, phrases in table.items()}
    for router, table in ROUTERS
}


def match(prompt):
    """Return [(router, [reference files], [matched phrases])] for every router that hit."""
    hits = []
    for router, table in ROUTERS:
        refs, matched = [], []
        for ref, phrases in table.items():
            for phrase, pat in zip(phrases, PATTERNS[router][ref]):
                if pat.search(prompt):
                    matched.append(phrase)
                    if ref not in refs:
                        refs.append(ref)
        if refs:
            hits.append((router, refs, matched))
    return hits


def main():
    prompt = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace")).get("prompt", "")
    hits = match(prompt)
    if not hits:
        return
    parts = []
    for router, refs, matched in hits:
        parts.append(
            "Invoke the `{}` skill and read {} before answering "
            "(matched: {}).".format(
                router,
                ", ".join("`references/{}`".format(r) for r in refs),
                ", ".join(sorted(set(matched))[:6]),
            )
        )
    if len(hits) > 1:
        parts.append("This task spans both routers -- read both SKILL.md files.")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": " ".join(parts),
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail open: never break the session
    sys.exit(0)
