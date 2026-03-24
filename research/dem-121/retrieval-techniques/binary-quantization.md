# Binary Quantization

## Overview
- **Category:** Embedding compression / storage optimization
- **Key papers/implementations:** "Efficient Passage Retrieval with Hashing for Open-Domain Question Answering" — Yamada et al. (ACL 2021). Practical adoption driven by Qdrant, Weaviate, and Vespa blog posts (2023-2024). Cohere and Mixedbread ship models explicitly optimized for binary quantization.
- **Maturity:** Production-proven — supported natively by Qdrant, Weaviate, Milvus, and Vespa; widely deployed for cost reduction at scale

## How It Works

Binary quantization converts each dimension of a floating-point embedding vector to a single bit: 1 if the value is ≥ 0, 0 otherwise. A 1024-dimensional float32 embedding (4096 bytes) becomes a 1024-bit vector (128 bytes) — a **32x storage reduction**.

```python
# Binary quantization
def binary_quantize(embedding):
    return [1 if x >= 0 else 0 for x in embedding]

# Similarity via Hamming distance (XOR + popcount)
def binary_similarity(bq_a, bq_b):
    # Count matching bits — fast CPU operation
    xor_result = bq_a ^ bq_b
    hamming_distance = popcount(xor_result)
    return len(bq_a) - hamming_distance  # matching bits = similarity
```

**Retrieval pattern (oversampling + rescoring):**
1. Use binary vectors for fast initial candidate retrieval via Hamming distance (bitwise XOR + popcount — extremely fast on modern CPUs)
2. Retrieve `k * oversampling_factor` candidates (typically 3-10x oversampling)
3. Rescore top candidates against original float32 vectors for final ranking

This two-phase approach recovers most of the quality loss from quantization. The binary search is so fast that 10x oversampling still outperforms float32 ANN search in wall-clock time.

**Why it works:** For high-dimensional embeddings (≥768d), the sign of each dimension carries significant discriminative information. Models trained with Matryoshka or specifically optimized for binary quantization front-load information into the sign bit, making binary quantization even more effective.

## Relevance to Code Retrieval
- **Applicable to Kenjutsu?** Yes — large codebase indexing creates significant storage/memory pressure that binary quantization directly addresses
- **Which pipeline stage?** Retrieval (index compression and fast candidate generation)
- **Complementary or replacement?** Complementary — an optimization layer on top of any dense embedding approach

### Code-Specific Strengths
- **Scale enabler**: A codebase with 10M function-level chunks at 1024d float32 requires ~40GB of vector storage; binary quantization reduces this to ~1.25GB, making in-memory retrieval feasible
- **Fast pre-filtering**: Binary search can quickly narrow candidates before expensive operations (reranking, cross-encoder scoring) — critical when the code search corpus is large
- **Cost-effective multi-index**: Enables maintaining multiple embedding indices (e.g., function-level + file-level + docstring-level) at manageable storage cost

### Code-Specific Limitations
- **Quality loss on subtle semantic queries**: Binary quantization preserves coarse-grained similarity but loses fine distinctions — queries requiring nuanced semantic understanding of code logic may suffer
- **Dependent on embedding model**: Models not optimized for binary quantization may lose 10-20% recall; models trained for it (Cohere embed-v3, Mixedbread) lose only 3-5%
- **Not useful alone**: Must be combined with oversampling + rescoring to be practical; adds pipeline complexity

## Known Implementations
- **Qdrant** — native binary quantization with configurable oversampling and rescoring (production-ready)
- **Weaviate** — binary quantization via `bq` compression config (production-ready)
- **Milvus** — supports binary vectors with Hamming/Jaccard distance
- **Vespa** — binary embeddings with bitwise operations
- **NumPy/custom** — trivial to implement: `np.packbits((embedding > 0).astype(np.uint8))`

## Trade-offs

### Pros
- **32x storage reduction** — the most aggressive compression available for dense embeddings
- **10-30x faster distance computation** — Hamming distance via XOR + popcount is orders of magnitude faster than float32 cosine/dot-product
- **Minimal quality loss with rescoring** — oversampling + float32 rescore recovers 95-99% of original recall
- **In-memory feasibility** — brings billion-scale vector indices into RAM on commodity hardware
- **Dead simple implementation** — `sign(x)` per dimension; no codebook training, no clustering

### Cons
- **Quality loss without rescoring** — raw binary retrieval loses 10-25% recall depending on model; rescoring is mandatory
- **Requires float32 storage for rescoring** — you still need the original vectors (or scalar-quantized versions) for the rescore step, so total storage isn't just 128 bytes/vector
- **Oversampling tuning** — optimal oversampling factor varies by dataset and query type; requires experimentation
- **Model-dependent effectiveness** — embedding models not trained for binary quantization produce worse results; constrains model choice
- **Complexity cost:** Low — most vector databases handle it natively; custom implementation is ~10 lines of code

## Composability

| Technique | Compatible? | Notes |
|-----------|------------|-------|
| Matryoshka embeddings | Yes, excellent | Truncate dimensions first, then binary quantize for compound compression |
| Scalar quantization | Alternative | Typically choose one or use binary for first-pass, scalar for rescore |
| Hybrid BM25 + dense | Yes | Binary quantization affects only the dense vector side |
| Late chunking | Yes | Quantize the output embeddings regardless of how they were produced |
| Reranking | Yes, recommended | Binary retrieval → rescore → reranker is the intended pipeline |
| ColBERT | No | ColBERT uses per-token vectors with its own compression (ColBERTv2 residuals) |

## Verdict for Kenjutsu
- **Recommendation:** ADOPT
- **Priority:** Layer 2 — implement once the embedding model is selected and index size becomes a concern
- **Rationale:** Binary quantization is a nearly free optimization that becomes essential at scale. Kenjutsu should select an embedding model that performs well under binary quantization (Matryoshka-capable models are ideal candidates) and plan the retrieval pipeline to support oversampling + rescoring from the start. This isn't an MVP requirement — initial development can use full float32 vectors — but the pipeline architecture should not preclude adding binary quantization later. When the index grows beyond what fits comfortably in memory, this is the first optimization to reach for.
