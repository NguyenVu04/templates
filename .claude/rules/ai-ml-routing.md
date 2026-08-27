# ML and LLM work goes through a router skill

Two router skills cover this ground. Read the router's `SKILL.md` first — it holds the
cross-cutting rules — then only the `references/*.md` files it points at.

- **`ai-engineering`** — anything built on top of an LLM: prompts, structured output, RAG,
  agents and tool use, evals, fine-tuning, self-hosted serving.
- **`machine-learning`** — classical ML and PyTorch: EDA and splitting, architecture, training,
  interpretability, evaluation and deployment, experiments, statistics.

Fine-tuning an open-weight model is `ai-engineering`. Training a model from scratch is
`machine-learning`. A task spanning both reads both routers. Do not answer an ML or LLM question
from general knowledge when the relevant reference file has not been read.
