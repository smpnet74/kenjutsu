# Arctic Embed

**Provider:** Snowflake
**Category:** General-purpose embedding model family (retrieval-optimized)
**Date evaluated:** 2026-03-23
**Parent issue:** DEM-123

---

## 1. Model Overview

Arctic Embed is a family spanning three generations. The v2.0 models represent the current state.

### v1.0 Family (April 2024)

| Variant | Base Model | Params | Dims | Context | License |
|---|---|---|---|---|---|
| arctic-embed-xs | MiniLM-L6 | 23M | 384 | 512 | Apache 2.0 |
| arctic-embed-s | e5-small | 33M | 384 | 512 | Apache 2.0 |
| arctic-embed-m | e5-base | 110M | 768 | 512 | Apache 2.0 |
| arctic-embed-m-long | nomic-embed-text-v1 | 137M | 768 | 2048 (8192 w/ RoPE) | Apache 2.0 |
| arctic-embed-l | e5-large | 335M | 1024 | 512 | Apache 2.0 |

### v1.5 (September 2024)

| Variant | Params | Dims | Context |
|---|---|---|---|
| arctic-embed-m-v1.5 | 109M | 768 | 512 |

### v2.0 (December 4, 2024) — Current

| Variant | Base Model | Params (total) | Dims | Context | License |
|---|---|---|---|---|---|
| arctic-embed-m-v2.0 | GTE-multilingual-base | 305M | 768 | 8,192 | Apache 2.0 |
| arctic-embed-l-v2.0 | BAAI/bge-m3-retromae | 568M | 1024 | 8,192 | Apache 2.0 |

HuggingFace: `Snowflake/snowflake-arctic-embed-*`

## 2. Benchmark Performance

### MTEB Retrieval Scores (BEIR nDCG@10)

Snowflake only reports retrieval scores — no full MTEB suite evaluation.

| Variant | BEIR nDCG@10 | MIRACL | CLEF |
|---|---|---|---|
| arctic-embed-xs | 50.15 | — | — |
| arctic-embed-s | 51.98 | — | — |
| arctic-embed-m | 54.90 | — | — |
| arctic-embed-l | 55.98 | — | — |
| arctic-embed-m-v1.5 | 55.14 | — | — |
| arctic-embed-m-v2.0 | 55.4 | 55.2 | 51.7 |
| arctic-embed-l-v2.0 | 55.6 | 55.8 | 52.9 |

**Overall MTEB, Classification, Clustering, STS:** Not available — not evaluated.

### Code-Specific Benchmarks

None published. No CodeSearchNet, CoSQA, or CoIR results in official documentation or papers. Training data includes StackExchange and S2ORC (code-adjacent) but code retrieval is not benchmarked.

## 3. Technical Capabilities

| Capability | v1.0 | v1.5 | v2.0 |
|---|---|---|---|
| Matryoshka (MRL) | No | Yes (min 256 dims) | Yes (min 256 dims) |
| Quantization (QAT) | No | Yes (Int8: ~0% loss; Int4: ~2% loss) | Yes |
| Instruction-tuned | No prefix | `"Represent this sentence..."` prefix | `query:` prefix |
| Multi-lingual | English only | English only | 74 languages |
| Sparse + dense | Dense only | Dense only | Dense only |

v2.0 with MRL + Int4 achieves **128 bytes/vector** at 256 dimensions — excellent for large-scale indexing.

## 4. Deployment & Infrastructure

### Self-Hosted

| Variant | FP16 VRAM | INT8 VRAM |
|---|---|---|
| arctic-embed-m / m-v1.5 (~110M) | ~0.22 GB | ~0.11 GB |
| arctic-embed-m-v2.0 (305M) | ~0.6 GB | ~0.3 GB |
| arctic-embed-l (335M) | ~0.67 GB | ~0.34 GB |
| arctic-embed-l-v2.0 (568M) | ~1.1 GB | ~0.55 GB |

Official throughput: >100 docs/sec on NVIDIA A10 GPU; sub-10ms query latency.

### Managed API

| Provider | Notes |
|---|---|
| Snowflake Cortex | ~$0.05 credits/1M tokens (m and m-v1.5 available) |
| NVIDIA NIM | arctic-embed-l was listed but deprecated 2025-12-19 |
| HuggingFace Inference API | Available for l-v2.0 |

### Framework Support

sentence-transformers, HuggingFace Transformers, Transformers.js, ONNX, GGUF (community), Safetensors, TEI.

## 5. Code Retrieval Suitability

**Strengths:**
- Excellent compression (MRL + Int4 = 128 bytes/vector) — critical for large codebases
- v2.0 has 8,192-token context window
- Very lightweight — all variants run on modest hardware
- 74-language support in v2.0
- Apache 2.0 license
- Purpose-built for retrieval (not general-purpose MTEB-optimized)
- Official throughput benchmarks show production readiness

**Weaknesses:**
- No published code retrieval benchmarks — capability is unverified
- No full MTEB evaluation — only retrieval subset reported
- Dense only — no sparse retrieval for keyword matching
- NVIDIA NIM endpoint was deprecated
- Code retrieval performance is speculative based on general retrieval scores

**Comparison to code-specialized models:**
Cannot be directly compared — no code benchmarks exist. General retrieval scores (55.6 BEIR for l-v2.0) are competitive but not indicative of code performance per CoIR findings.

**Multi-language code support:** v2.0's 74-language support could benefit multilingual documentation, but no code-specific training is documented.

## 6. Overall Assessment

| Field | Value |
|---|---|
| Recommendation | **Worth considering — pending code retrieval validation** |
| Best use case | High-throughput document indexing with aggressive compression; potential secondary model for bulk embedding |
| Key trade-offs | Best compression options (MRL + QAT) and excellent throughput, but unverified code retrieval capability |

Arctic Embed v2.0's standout feature is its compression pipeline — MRL down to 256 dims + Int4 quantization yields 128 bytes/vector with only ~2% quality loss. For a code review tool indexing millions of code chunks, this storage efficiency is valuable. However, code retrieval capability is completely unverified. If code retrieval performance validates, arctic-embed-l-v2.0 would be an excellent choice for the indexing/storage layer. **Recommend running a local CoIR or CodeSearchNet evaluation before committing.**
