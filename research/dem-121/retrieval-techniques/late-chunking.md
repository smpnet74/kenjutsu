# Late Chunking

## Overview
- **Category:** Embedding strategy / chunking
- **Key papers/implementations:** "Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models" — Jina AI (arXiv 2409.04701, October 2024). Companion blog post on jina.ai. Builds on long-context embedding model trend (Jina v2/v3, Nomic).
- **Maturity:** Early production — shipped in Jina's embedding API; not yet a default in major RAG frameworks

## How It Works

Late chunking inverts the traditional RAG pipeline from **chunk-then-embed** to **embed-then-chunk**. The entire document (up to the model's context window) is passed through a long-context transformer encoder to produce token-level embeddings where every token's representation is contextualized by the full document via self-attention. Chunk boundaries are then applied to this output embedding matrix, and each chunk's final embedding is produced by mean-pooling the contextualized token embeddings within that span.

This solves a fundamental problem with traditional chunking: when a chunk contains a pronoun like "It" or a function call like `helper_function()`, the embedding has no awareness of what those refer to if the referent is in a different chunk. With late chunking, the transformer's self-attention has already resolved these dependencies before the pooling step.

**Pseudocode:**
```python
# Traditional: chunk → embed (context lost)
chunks = split_document(document)
embeddings = [model.encode(chunk) for chunk in chunks]

# Late chunking: embed → chunk (context preserved)
token_embeddings = model.encode_tokens(document)  # [seq_len, hidden_dim]
chunk_spans = get_chunk_boundaries(document)       # [(start, end), ...]
embeddings = [mean_pool(token_embeddings[s:e]) for s, e in chunk_spans]
```

The key constraint is that this requires a **long-context embedding model** (8K+ tokens) — standard 512-token BERT/sentence-transformers are too short to be useful. Models like jina-embeddings-v2 (8K), jina-embeddings-v3, and Nomic-embed (8K) support this.

## Relevance to Code Retrieval
- **Applicable to Kenjutsu?** Yes — code has dense cross-references (imports, function calls, type propagation, class inheritance) that create exactly the kind of cross-chunk dependencies late chunking resolves
- **Which pipeline stage?** Indexing (embedding generation)
- **Complementary or replacement?** Replacement for the chunk-then-embed step; complementary to everything else in the pipeline

### Code-Specific Strengths
- **Import context propagation**: Module imports at file top provide critical context for every function below — late chunking preserves this
- **Docstring ↔ implementation linking**: When a function's docstring and body land in different chunks, late chunking maintains the semantic connection
- **Type resolution**: Understanding what a variable is requires context from its declaration, which may be in a different chunk span
- **Best combined with AST-aware chunking**: Let the AST define where to chunk (function/class boundaries), but use late chunking to ensure each chunk's embedding is informed by the full file context

### Code-Specific Limitations
- **Cross-file context is NOT addressed**: Late chunking operates within a single document/file. It does not help with cross-file dependencies (function defined in `utils.py` called in `main.py`). Graph-based or cross-file retrieval strategies are still needed.
- **Large files exceed context windows**: Source files >8K tokens still need segmentation before late chunking, losing some benefit
- **AST-aware chunking already captures some of this**: Code's well-defined structure means AST-aware chunking already recovers much of the structural context that late chunking provides for prose. The marginal benefit over AST-aware chunking is smaller than the benefit over naive chunking

## Known Implementations
- **Jina AI API** — native support via `late_chunking` parameter in jina-embeddings-v2/v3 (production-ready)
- **Hugging Face / custom** — ~20 lines of Python: tokenize full document, forward pass for `last_hidden_state`, determine chunk boundary token indices, mean-pool each span
- **LlamaIndex** — available through JinaEmbedding integration class; not a built-in core feature of the general embedding pipeline
- **LangChain** — available through Jina integration; no first-class `LateChunkingEmbeddings` class in core

## Trade-offs

### Pros
- **No storage overhead** — each chunk still produces one vector of the same dimensionality, unlike overlap-based chunking which increases storage proportionally
- **No LLM calls** — unlike contextual retrieval (Anthropic's approach), context enrichment is free at inference time
- **Drop-in improvement** — the resulting chunk embeddings are standard vectors; downstream retrieval and reranking are unaffected
- **5-15% recall@10 improvement** over naive fixed-size chunking with the same base model (per Jina's evaluations)
- **Strongest on context-dependent documents** — high cross-reference density, long documents, queries that span chunk boundaries

### Cons
- **Requires long-context embedding model** — biggest practical constraint; ties embedding model selection to models supporting 8K+ context
- **Higher indexing latency** — O(n^2) attention over full document instead of parallelizable small-chunk encoding; 8K token document is significantly more expensive than 16 x 512-token chunks
- **Pipeline coupling** — embedding and chunking steps can no longer be independent; chunk boundaries must map to token indices via tokenizer offset mapping
- **Marginal over sophisticated baselines** — improvement narrows when compared against chunking with large overlap windows (which partially recover cross-chunk context, albeit at storage cost)
- **Memory during indexing** — must hold full document token embeddings (`[seq_len, hidden_dim]`, e.g., 8192 x 768 ≈ 25MB float32 per document)
- **Complexity cost:** Low-Medium — simple with Jina API, moderate for DIY implementation

## Composability

| Technique | Compatible? | Notes |
|-----------|------------|-------|
| Hybrid BM25 + dense | Yes | Chunk text unchanged; only dense embedding improves |
| Reranking | Yes | Better first-stage recall → better candidate set for reranker |
| HyDE | Yes | Corpus-side embeddings independent of query-side strategy |
| Contextual retrieval | Partially redundant | Both inject context into chunk embeddings; combining adds cost with diminishing returns |
| Parent-child retrieval | Partially redundant | Late chunking bakes parent context into child embedding; parent expansion still useful for generation context |
| Matryoshka / quantization | Yes | Output embeddings are standard vectors; all post-processing applies |
| Knowledge graphs | Orthogonal | Late chunking improves vector retrieval; graphs handle structural/relational queries |

## Verdict for Kenjutsu
- **Recommendation:** EVALUATE
- **Priority:** Layer 2 — adopt after core pipeline (hybrid search, reranking) is established
- **Rationale:** Low-cost improvement over naive chunking that requires no LLM calls and no storage overhead, but Kenjutsu should first invest in AST-aware chunking (which captures much of the same benefit for code) and hybrid search. Late chunking becomes a compelling incremental gain once the embedding model is chosen — especially if Jina v3 is selected, where it's a free parameter toggle. The cross-file limitation means it doesn't solve Kenjutsu's hardest retrieval problem (multi-file code understanding).
