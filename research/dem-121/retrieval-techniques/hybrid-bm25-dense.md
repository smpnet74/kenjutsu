# Hybrid BM25 + Dense Retrieval

## Overview
- **Category:** Search fusion
- **Key papers/implementations:** "Sparse, Dense, and Attentional Representations for Text Retrieval" — Luan et al. (TACL 2021). "A Thorough Examination of the Recall-Efficiency Tradeoff in Neural vs. Traditional Retrieval" — Lin & Ma (ECIR 2021). Reciprocal Rank Fusion (RRF) — Cormack et al. (SIGIR 2009). Production implementations in Vespa, Elasticsearch 8+, Weaviate, Qdrant, LlamaIndex, and LangChain.
- **Maturity:** Production-proven — standard architecture in modern search systems; default recommendation in every major RAG framework

## How It Works

Hybrid search combines two complementary retrieval paradigms:

1. **BM25 (sparse/lexical):** Token-matching algorithm that scores documents based on term frequency, inverse document frequency, and document length normalization. Excels at exact keyword matching and rare term retrieval.

2. **Dense retrieval (semantic):** Embedding-based similarity search using vector representations. Excels at semantic matching — finding documents that are conceptually related even without shared vocabulary.

**Fusion strategies:**

**Reciprocal Rank Fusion (RRF)** — the most common and robust approach:
```python
def rrf_score(doc, rankings, k=60):
    """Combine rankings from multiple retrieval systems."""
    score = 0
    for ranking in rankings:
        if doc in ranking:
            rank = ranking.index(doc) + 1  # 1-indexed
            score += 1.0 / (k + rank)
    return score

# Example: doc ranked #3 by BM25 and #7 by dense
# RRF = 1/(60+3) + 1/(60+7) = 0.0159 + 0.0149 = 0.0308
```

**Weighted linear combination:**
```python
# Normalize scores to [0, 1] from each system
final_score = alpha * bm25_score_normalized + (1 - alpha) * dense_score_normalized
# alpha typically 0.3-0.5 for general text; needs tuning per domain
```

**RRF vs. weighted sum:** RRF is rank-based (doesn't require score normalization) and is more robust to score distribution differences between systems. Weighted sum can outperform RRF when carefully tuned but is brittle to score distribution shifts. **For code search, RRF is the safer default.**

## Relevance to Code Retrieval
- **Applicable to Kenjutsu?** Yes — this is the foundational retrieval architecture for Kenjutsu
- **Which pipeline stage?** Retrieval (combines two first-stage retrievers)
- **Complementary or replacement?** Foundational — the base layer on which other techniques build

### Code-Specific Strengths
- **BM25 excels at code identifiers**: Function names, class names, variable names, API calls, error messages — these are effectively "keywords" that BM25 matches precisely. A query for `parseJSONResponse` will match that exact identifier via BM25 even if the dense model doesn't embed it well.
- **Dense excels at intent matching**: "function that converts temperature from Celsius to Fahrenheit" matches semantic intent even when the code uses `temp_convert` or `c_to_f` as identifiers.
- **Coverage of both query types**: Code search queries range from exact identifier lookups ("where is `handleAuth` called?") to semantic intent ("retry logic with exponential backoff"). Neither BM25 nor dense alone covers both well.
- **Error message retrieval**: BM25 is critical for matching exact error strings — users often paste error messages as queries.

### Code-Specific Considerations
- **BM25 tokenization for code**: Standard BM25 tokenizers split on whitespace and punctuation, which mangles `camelCase`, `snake_case`, and dot-separated identifiers (`module.function.method`). Code-aware tokenization is essential: split on case boundaries, underscores, dots, and common delimiters while preserving the full token.
- **Optimal alpha for code**: Empirical evidence suggests code search benefits from higher BM25 weight (alpha ≈ 0.5-0.7) compared to general NL search (alpha ≈ 0.3), because exact identifier matching is so important. However, this is model-dependent — evaluate with Kenjutsu's specific queries.
- **SPLADE as sparse alternative**: Learned sparse models like SPLADE can replace BM25 with potentially better semantic sparse representations. However, SPLADE models trained on code are scarce, and BM25's simplicity and proven effectiveness make it the safe choice.

### Code-Specific Limitations
- **BM25 vocabulary mismatch**: If the query uses different terminology than the code (e.g., "login" vs. `authenticate`), BM25 contributes nothing — the dense model must carry the retrieval alone
- **BM25 on minified/obfuscated code**: Compressed JavaScript or obfuscated code defeats lexical matching entirely
- **Language-specific tuning**: Optimal BM25 parameters (k1, b) may differ between programming languages due to different token distributions

## Known Implementations
- **Vespa** — native hybrid search with configurable rank profiles; production-grade
- **Elasticsearch 8+** — kNN search combined with BM25 via `sub_searches` and RRF
- **Weaviate** — `hybrid` search mode with configurable alpha (BM25 weight)
- **Qdrant** — sparse+dense hybrid via named vectors (v1.7+)
- **LlamaIndex** — `QueryFusionRetriever` with RRF; BM25 via `BM25Retriever`
- **LangChain** — `EnsembleRetriever` with RRF fusion
- **Typesense** — hybrid search with semantic + keyword matching

## Trade-offs

### Pros
- **Consistent quality improvement** — hybrid retrieval consistently outperforms either BM25 or dense alone across benchmarks (typically 5-15% recall improvement)
- **Robustness** — failures in one retrieval path are compensated by the other; no single point of weakness
- **Interpretable** — BM25 results explain "which keywords matched"; dense results explain "why it's semantically relevant"
- **Mature ecosystem** — every major search engine and RAG framework supports it out of the box
- **Low incremental cost** — BM25 is computationally cheap; adding it to an existing dense retrieval pipeline is minimal overhead

### Cons
- **Two indices to maintain** — both a BM25 inverted index and a vector index, increasing storage and indexing complexity
- **Fusion tuning** — optimal alpha (for weighted sum) or k parameter (for RRF) varies by domain; requires evaluation
- **Latency addition** — two retrieval paths + fusion adds latency vs. single-path retrieval (typically 10-30ms additional)
- **Code tokenization is non-trivial** — getting BM25 to work well on code requires custom tokenization, which is development effort beyond "plug in Elasticsearch"
- **Complexity cost:** Low-Medium — RRF is simple; code-aware BM25 tokenization is the main engineering effort

## Composability

| Technique | Compatible? | Notes |
|-----------|------------|-------|
| Reranking | Yes, standard | Hybrid retrieval → reranker is the canonical RAG pipeline |
| Late chunking | Yes | Improves the dense retrieval side; BM25 unaffected |
| HyDE | Yes | HyDE expands the dense query; BM25 uses the original query |
| Contextual retrieval | Yes | Context prepended to chunks improves both BM25 (more keywords) and dense (more context) |
| ColBERT | Yes | ColBERT replaces the dense side of the hybrid |
| Binary/scalar quantization | Yes | Quantization compresses the dense index; BM25 index unaffected |
| Parent-child retrieval | Yes | Hybrid retrieval at child level, parent expansion for context |

## Verdict for Kenjutsu
- **Recommendation:** ADOPT
- **Priority:** MVP — this is the foundational retrieval architecture
- **Rationale:** Hybrid BM25 + dense retrieval is the single most impactful retrieval technique for Kenjutsu and should be the core of the MVP pipeline. Code search fundamentally requires both exact identifier matching (BM25) and semantic intent matching (dense). Use RRF fusion as the default (robust, no tuning required), with the option to evaluate weighted combination later. The primary engineering investment is code-aware BM25 tokenization — splitting on camelCase/snake_case/dots while preserving full identifiers as tokens. Every other technique in this evaluation builds on top of this foundation.
