# Late Interaction (ColBERT / ColPali)

## Overview
- **Category:** Interaction model / retrieval
- **Key papers/implementations:** "ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT" — Khattab & Zaharia (SIGIR 2020). "ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction" — Santhanam et al. (NAACL 2022). "ColPali: Efficient Document Retrieval with Vision Language Models" — Faysse et al. (2024). RAGatouille library (2024).
- **Maturity:** Production-proven — ColBERTv2 widely deployed; RAGatouille provides accessible Python interface; Vespa and Qdrant have native ColBERT support

## How It Works

Late interaction separates the query and document encoding phases (like bi-encoders for speed) but preserves token-level representations instead of collapsing to a single vector. At retrieval time, it computes fine-grained similarity between every query token embedding and every document token embedding using a MaxSim operator.

**Encoding phase (offline for documents, online for queries):**
Each document is independently encoded through a BERT-like transformer, producing one embedding per token: `D = BERT(doc) → [d₁, d₂, ..., dₙ]`. Similarly for queries: `Q = BERT(query) → [q₁, q₂, ..., qₘ]`.

**Retrieval phase (online):**
For each query token `qᵢ`, compute its maximum cosine similarity against all document tokens: `MaxSim(qᵢ, D) = max(cos(qᵢ, dⱼ))` for all `j`. The final relevance score is the sum of MaxSim values across all query tokens: `Score(Q, D) = Σᵢ MaxSim(qᵢ, D)`.

```python
# Pseudocode
def colbert_score(query_embeddings, doc_embeddings):
    # query_embeddings: [num_query_tokens, dim]
    # doc_embeddings: [num_doc_tokens, dim]
    sim_matrix = cosine_similarity(query_embeddings, doc_embeddings)  # [m, n]
    max_sim_per_query_token = sim_matrix.max(dim=1)  # [m]
    return max_sim_per_query_token.sum()
```

This "late interaction" pattern captures token-level matching signals that single-vector models lose. A query for `"async error handling"` can match the exact tokens `async` and `error` in the document independently, then aggregate — rather than hoping the single-vector dot product captures this.

**ColBERTv2 optimizations:** Residual compression reduces per-token storage from 128 floats to ~2 bytes via centroids + residual quantization. Denoised supervision improves training. These make ColBERT practical at scale.

## Relevance to Code Retrieval
- **Applicable to Kenjutsu?** Yes — code retrieval benefits strongly from token-level matching since code queries often contain exact identifiers, API names, and syntactic patterns
- **Which pipeline stage?** Retrieval (replaces or augments single-vector retrieval)
- **Complementary or replacement?** Can replace single-vector dense retrieval, or serve as a reranking-like refinement stage over initial candidates

### Code-Specific Strengths
- **Exact identifier matching with semantic context**: ColBERT can match `parseJSON` in the query to `parseJSON` in the document while also matching semantic neighbors — combining keyword-like precision with embedding-like recall
- **Multi-aspect queries**: A query like "async function that handles HTTP errors" has three distinct aspects (async, HTTP, error handling) — MaxSim naturally decomposes this into per-token matches
- **Robust to naming conventions**: Token-level matching can bridge `camelCase` and `snake_case` patterns when the underlying tokens align

### Code-Specific Limitations
- **Storage overhead**: Multi-vector storage is 100-200x larger than single-vector per document before compression (one vector per token vs. one per chunk)
- **Not trained on code by default**: ColBERTv2 is trained on MS MARCO (natural language). Code-specific fine-tuning is needed for optimal performance
- **Query latency**: MaxSim computation over large collections requires specialized indexing (PLAID, Vespa) — not a simple ANN lookup

## Known Implementations
- **RAGatouille** — Python library wrapping ColBERTv2 with simple `index()` and `search()` API; good for prototyping (active development)
- **Vespa** — production-grade support for ColBERT via `colbert` rank profile; handles PLAID-like indexing natively
- **Qdrant** — multi-vector support enabling ColBERT-style storage and retrieval (v1.7+)
- **LlamaIndex** — `ColbertIndex` integration available via RAGatouille bridge
- **Stanford ColBERT repo** — reference implementation with PLAID indexing engine

## Trade-offs

### Pros
- **Best-in-class retrieval quality** — consistently outperforms single-vector models on BEIR and MS MARCO benchmarks
- **Interpretable matching** — token-level similarity matrix reveals exactly which query terms matched which document terms, enabling debugging
- **No information bottleneck** — avoids compressing document semantics into a single vector
- **Graceful degradation** — even without code-specific training, token overlap signals help for code (identifiers are "keywords" the model preserves)

### Cons
- **Storage cost** — even with ColBERTv2 compression (~2 bytes/token), a 500-token chunk stores ~1KB of embeddings vs. ~0.5KB for a single 128-dim float32 vector. At millions of chunks, this matters.
- **Indexing complexity** — PLAID or centroid-based indexing required for sub-linear retrieval; more complex than standard HNSW
- **Query latency** — 10-50ms vs. 1-5ms for single-vector ANN (acceptable for most applications, problematic for ultra-low-latency)
- **No off-the-shelf code model** — requires fine-tuning on code data for best results; no public "ColBERT-code" model exists
- **Complexity cost:** Medium-High — RAGatouille simplifies prototyping, but production deployment requires Vespa/Qdrant expertise and careful storage planning

## Composability

| Technique | Compatible? | Notes |
|-----------|------------|-------|
| Hybrid BM25 + dense | Yes | ColBERT replaces the dense component; BM25 still valuable for exact keyword matches |
| Late chunking | Partially | Late chunking produces single vectors; ColBERT needs token-level embeddings — different paradigms |
| Reranking (cross-encoder) | Yes | ColBERT as first-stage → cross-encoder reranking of top-k; common pattern |
| HyDE | Yes | HyDE generates query expansion; ColBERT scores the expanded query at token level |
| Matryoshka / quantization | Partially | ColBERTv2 has its own compression; standard Matryoshka doesn't apply to multi-vector |
| Contextual retrieval | Orthogonal | Context prepended to chunks before encoding; ColBERT then encodes the enriched text |

## Verdict for Kenjutsu
- **Recommendation:** EVALUATE
- **Priority:** Layer 2 — evaluate after core hybrid search pipeline is established
- **Rationale:** ColBERT's token-level matching is theoretically ideal for code retrieval where exact identifiers matter alongside semantic understanding. However, the storage overhead, lack of a code-specific pre-trained model, and indexing complexity make it a Layer 2 investment. Start with single-vector dense + BM25 hybrid, then evaluate ColBERT as a quality upgrade path when retrieval quality needs to improve beyond what reranking provides. RAGatouille makes prototyping feasible for benchmarking against the simpler pipeline.
