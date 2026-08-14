---
name: rag-pipeline
description: Design, build, and evaluate Retrieval-Augmented Generation (RAG) systems — document chunking, embeddings, vector databases (FAISS/Qdrant/pgvector/Chroma), hybrid search with BM25, reranking, and RAG-specific evaluation. Use this skill whenever the user wants an LLM to answer questions over their own documents/knowledge base, mentions "RAG", "vector search", "semantic search", "embedding", "chatbot đọc tài liệu", "hỏi đáp trên tài liệu nội bộ", or complains that their RAG system retrieves wrong passages or the model answers from the wrong context.
---

# RAG Pipeline

RAG quality is retrieval quality. When a RAG system gives bad answers, the retrieved context was wrong ~80% of the time — debug retrieval before touching prompts or models. Build the pipeline so retrieval is inspectable and measurable on its own.

## Architecture

```
Ingestion:  docs → parse → chunk → embed → index (+ metadata)
Query:      question → [rewrite] → retrieve (dense + BM25) → rerank → top-k
Generation: prompt(question + chunks with citations) → answer → [verify]
```

Keep ingestion idempotent and re-runnable (content-hash per chunk to skip unchanged docs) — you WILL re-chunk and re-embed many times.

## Chunking

The most consequential and least glamorous decision:
- Default: **recursive character/token splitting, 300–800 tokens, 10–15% overlap**, splitting on structure boundaries (headings → paragraphs → sentences) before hard cuts.
- Respect semantic units: never split a table, code block, or list mid-way; keep a heading attached to its section text (prepend the heading path — "Doc > Chapter > Section" — into each chunk; this alone lifts retrieval noticeably).
- **Small-to-big pattern**: embed small chunks (precise matching) but return the parent section to the LLM (sufficient context). Store `parent_id` in metadata.
- PDF parsing is a project of its own: use a proper parser (pymupdf/unstructured/docling), check output on scanned pages, tables, multi-column layouts — garbage parsing poisons everything downstream.
- Attach metadata to every chunk: source, title, section path, date, access level. You'll need it for filtering, citation, and debugging.

## Embeddings & index

- Pick embedding models from the MTEB retrieval leaderboard for your language(s); verify multilingual support explicitly for Vietnamese or mixed-language corpora. Note the model's max sequence length — chunks beyond it get truncated silently.
- Many models require prefixes ("query: ...", "passage: ...") — read the model card; skipping them costs real accuracy.
- **Embedding model version is part of the index**: query and documents must use the identical model; changing models means full re-embedding. Record the model name in index metadata.
- Vector store: FAISS (local, library), Chroma/LanceDB (local, easy), Qdrant (production, filtering), **pgvector (already have Postgres? start here)**. Below ~1M vectors, flat/HNSW anything works — don't over-engineer the store; the wins are in chunking and reranking.
- Normalize embeddings and use cosine/inner-product consistently.

## Retrieval quality stack

Apply in order until quality suffices:
1. **Hybrid search**: dense + BM25, fused with RRF (reciprocal rank fusion). BM25 catches exact terms dense misses (IDs, error codes, names, acronyms) — hybrid is near-strictly better than either alone.
2. **Reranking**: over-retrieve (top 20–50) then rerank with a cross-encoder (e.g., bge-reranker) to final top 3–8. Usually the single biggest quality jump.
3. **Query rewriting**: LLM rewrites conversational queries into standalone search queries (resolve "it", "that error"); multi-query (3 paraphrases, union results) for recall; HyDE for tricky corpora.
4. **Metadata filtering**: apply hard filters (date range, product, access rights) in the store, not post-hoc.
5. Top-k and threshold: more chunks ≠ better — irrelevant chunks actively mislead generation. Tune k on the eval set; consider a similarity floor below which the system says "not found".

## Generation

- Prompt: instruct to answer **only from the provided context** and to say "I don't know / not in the documents" when the context doesn't contain the answer — the single most important line for faithfulness.
- Number the chunks and require citations `[1][3]` per claim; render sources in the UI. Citations enable trust AND debugging.
- Include chunk metadata (title, date) in the context — the model uses it to arbitrate conflicts (prefer newer, prefer authoritative source).
- Order chunks best-first; instructions at top, question at the end.

## Evaluation (non-negotiable)

Build a golden set of 30–100 (question → relevant chunk ids → reference answer). Source from real user questions when possible; LLM-generate synthetic Q/A from chunks to bootstrap, then human-filter.

Measure the stages SEPARATELY:
- **Retrieval**: hit rate@k / recall@k (is a gold chunk in top-k?), MRR. Cheap, fast, run on every chunking/model/k change.
- **Generation** (given retrieved context): faithfulness (is every claim supported by the context?) and answer relevance — LLM-as-judge with a rubric works (see `llm-evaluation` skill for judge design and calibration).
- End-to-end answer correctness vs reference — the headline number, but diagnose via the stage metrics.

Debugging playbook: bad answer → look at retrieved chunks. Gold chunk missing from top-k → retrieval problem (chunking? embeddings? need hybrid/rerank?). Gold chunk present but answer wrong → generation problem (prompt, chunk ordering, too much noise). Gold chunk doesn't exist → ingestion/coverage problem. Log retrieved chunk ids per query in production so failures arrive reproducible.

## Production notes

- Index updates: incremental upserts by content hash; schedule re-ingestion; tombstone deleted docs (stale chunks answering from deleted content is a real incident class).
- Access control: filter by user permissions at query time in the store — never rely on the LLM to withhold restricted content it was given.
- Cache (query embedding → results) for hot queries; embed queries and rerank on GPU or a fast endpoint if latency-sensitive.
- Cost sanity: reranking 50 chunks per query with a cross-encoder is cheap; sending 30 chunks to a large LLM is not — spend on retrieval precision to save on generation tokens.
