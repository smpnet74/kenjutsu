# Scalar Quantization

## Overview
- **Category:** Embedding compression / storage optimization
- **Key papers/implementations:** Standard signal processing technique applied to vector search. Widely adopted by Qdrant (2023), Weaviate, Milvus, pgvector, and Pinecone. Detailed analysis in Qdrant's "Quantization" documentation and Pinecone's INT8 quantization benchmarks.
- **Maturity:** Production-proven — default compression in most managed vector databases; well-understood quality/compression trade-offs

## How It Works

Scalar quantization maps each dimension of a float32 embedding to a lower-precision integer representation, typically INT8 (8-bit) or INT4 (4-bit). Unlike binary quantization (which preserves only the sign), scalar quantization preserves relative magnitude within each dimension.

**INT8 quantization (most common):**
For each dimension across the corpus, compute the min and max values. Map the float32 range `[min_d, max_d]` to `[0, 255]` using linear scaling:

```python
# Calibration (offline, per dimension)
min_vals = embeddings.min(axis=0)  # per-dimension min across corpus
max_vals = embeddings.max(axis=0)  # per-dimension max across corpus
scales = (max_vals - min_vals) / 255.0

# Quantization
def scalar_quantize_int8(embedding, min_vals, scales):
    return np.round((embedding - min_vals) / scales).astype(np.uint8)

# Dequantization (for rescoring)
def dequantize(quantized, min_vals, scales):
    return quantized.astype(np.float32) * scales + min_vals
```

**INT4 quantization:** Same principle but maps to `[0, 15]` — 8x compression vs. float32 (double the compression of INT8). Quality loss is higher but still manageable with rescoring.

**Key implementation detail:** Distance computation between INT8 vectors uses integer arithmetic (faster than float32 on many architectures) or SIMD-optimized routines. Some databases compute approximate distances directly on quantized vectors; others dequantize on-the-fly.

## Relevance to Code Retrieval
- **Applicable to Kenjutsu?** Yes — provides a balanced quality/compression trade-off for the primary vector index
- **Which pipeline stage?** Retrieval (index compression)
- **Complementary or replacement?** Complementary — an optimization layer; can also serve as the rescore target for binary quantization

### Code-Specific Strengths
- **Preserves semantic nuance**: Unlike binary quantization, INT8 retains relative distances well enough for code semantic queries — "find functions similar to this one" preserves fine-grained similarity rankings
- **4x compression with minimal quality loss**: 1024d float32 (4KB) → INT8 (1KB) with typically <2% recall loss — significant savings across large codebases
- **No oversampling needed**: Quality is high enough that standard retrieval (without oversampling + rescoring) often produces acceptable results, simplifying the pipeline

### Code-Specific Limitations
- **Less dramatic compression than binary**: 4x vs. 32x — if storage is the primary constraint, binary quantization may be necessary
- **Calibration sensitivity**: Min/max statistics must be computed from a representative sample of the corpus; if code embeddings have unusual distributions (e.g., bimodal from mixing documentation and code), calibration may be suboptimal
- **Not a substitute for good embeddings**: Quantization preserves relative ordering but cannot improve retrieval quality; the base embedding model must be good

## Known Implementations
- **Qdrant** — `ScalarQuantization` config with INT8; supports automatic calibration and rescoring
- **Weaviate** — product and scalar quantization options via compression config
- **Milvus** — IVF_SQ8 index type for scalar quantization
- **pgvector** — halfvec type for float16 (2x compression); INT8 via extensions
- **Pinecone** — automatic quantization in managed service
- **FAISS** — `IndexScalarQuantizer` with configurable bit widths (4, 6, 8 bit)

## Trade-offs

### Pros
- **4x storage reduction (INT8)** with typically <2% recall loss — the best quality/compression ratio available
- **8x storage reduction (INT4)** with ~5% recall loss — good middle ground between INT8 and binary
- **Faster distance computation** — integer arithmetic is faster than float32 on most hardware
- **No rescoring required** — unlike binary quantization, INT8 quality is often sufficient without a second pass
- **Universal support** — every major vector database supports scalar quantization; not tied to a specific vendor
- **Simple calibration** — just min/max statistics; no codebook training (unlike product quantization)

### Cons
- **Less compression than binary** — 4x vs. 32x; may not be sufficient for extremely large indices
- **Calibration step required** — must compute statistics from a representative corpus sample; not zero-config
- **INT4 quality can be problematic** — for high-precision retrieval tasks, INT4 may drop below acceptable thresholds
- **Distribution assumptions** — linear mapping assumes roughly uniform distribution per dimension; outliers waste quantization range
- **Complexity cost:** Very Low — most vector databases handle it with a single config flag

## Composability

| Technique | Compatible? | Notes |
|-----------|------------|-------|
| Matryoshka embeddings | Yes, excellent | Truncate first, then quantize for compound compression (e.g., 768d→256d→INT8 = 16x total) |
| Binary quantization | Yes | Use binary for first-pass, scalar-quantized vectors for rescoring (avoids storing float32) |
| Hybrid BM25 + dense | Yes | Scalar quantization affects only the dense vector side |
| Late chunking | Yes | Quantize the output embeddings regardless of how they were produced |
| Reranking | Yes | Scalar-quantized retrieval → cross-encoder reranking |
| ColBERT | No | ColBERT has its own residual compression; scalar quantization doesn't apply to multi-vector |
| Product quantization | Alternative | PQ offers better compression ratios but with more quality loss and complex training |

## Verdict for Kenjutsu
- **Recommendation:** ADOPT
- **Priority:** MVP — use as the default vector storage format from day one
- **Rationale:** INT8 scalar quantization is a no-regret optimization. The 4x storage reduction with <2% quality loss should be the default storage format for Kenjutsu's vector index. Unlike binary quantization (which requires an oversampling + rescoring pipeline), scalar quantization "just works" as a drop-in replacement for float32 storage. Combined with Matryoshka dimension reduction (e.g., 1024d→256d + INT8 = 16x total compression), this enables Kenjutsu to index large codebases affordably from the start. Keep float32 vectors available for calibration updates and quality benchmarking, but serve production queries from INT8.
