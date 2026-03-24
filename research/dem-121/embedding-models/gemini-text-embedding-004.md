# Gemini text-embedding-004 (and gemini-embedding-001 successor)

**Provider:** Google
**Category:** General-purpose embedding model (API-only, proprietary)
**Date evaluated:** 2026-03-23
**Parent issue:** DEM-123

---

## 1. Model Overview

### text-embedding-004 (DEPRECATED)

| Field | Value |
|---|---|
| Model name | text-embedding-004 |
| Provider | Google |
| Release date | May 14, 2024 |
| Architecture | Gecko — encoder-based transformer with bidirectional attention, distilled from large LLM |
| Parameters | ~1.2B |
| Dimensions | 768 (fixed) |
| Max context window | 2,048 tokens |
| License | Proprietary (API-only, no weights) |
| Category | General-purpose |
| Status | **Deprecated as of January 14, 2026** |

### gemini-embedding-001 (Current Replacement)

| Field | Value |
|---|---|
| Model name | gemini-embedding-001 |
| Provider | Google |
| Release date | October 31, 2025 (GA) |
| Architecture | Gemini LLM with bidirectional attention, mean pooling + linear projection |
| Parameters | Not publicly disclosed |
| Dimensions | 3072 default; MRL at 768, 1536, 3072 (128–3072 configurable) |
| Max context window | 2,048 tokens |
| License | Proprietary (API-only, no weights) |
| Category | General-purpose with strong code capability |

## 2. Benchmark Performance

### text-embedding-004 MTEB Scores

| Category | Score |
|---|---|
| Overall | 66.31 |
| Retrieval | 55.70 |
| Classification | 81.17 |
| STS | 85.06 |
| Clustering | Not published |

### gemini-embedding-001 MTEB Scores (from arXiv:2503.07891)

| Category | Score |
|---|---|
| Overall (Multilingual) | 68.32 — **#1 on MTEB Multilingual leaderboard** |
| Retrieval | 67.71 |
| Classification | 71.84 |
| Clustering | 54.99 |
| STS | 79.40 |
| Pair Classification | 83.64 |
| Reranking | 65.72 |

### Code-Specific Benchmarks

#### text-embedding-004

No code benchmarks published. Supports `CODE_RETRIEVAL_QUERY` task type but no performance data.

#### gemini-embedding-001

| Benchmark | Score |
|---|---|
| **CodeSearchNet (mean, 6 languages)** | **91.33** |
| **CoSQA** | **50.24** |
| **MTEB Code mean (12 tasks)** | **74.66** |

These are the strongest code retrieval scores of any model in this evaluation by a significant margin.

## 3. Technical Capabilities

| Capability | text-embedding-004 | gemini-embedding-001 |
|---|---|---|
| Matryoshka (MRL) | Not supported (fixed 768d) | **Yes** — 128–3072 configurable |
| Quantization | N/A (API-only) | N/A (API-only) |
| Instruction-tuned | Yes — 8 task type enums including `CODE_RETRIEVAL_QUERY` | Yes — same 8 task types |
| Multi-lingual | English-focused | **250+ languages** |
| Sparse + dense hybrid | Not supported | Not supported |

The `CODE_RETRIEVAL_QUERY` task type is a differentiator — it optimizes query embeddings specifically for code search, which self-hosted models cannot replicate without custom instruction-tuning.

## 4. Deployment & Infrastructure

### Self-Hosted

Not possible. API-only, no weights released.

### Managed API

| Model | Platform | Price per 1M tokens |
|---|---|---|
| text-embedding-004 | Google AI Studio | $0.020 |
| text-embedding-004 | Vertex AI | $0.10 |
| gemini-embedding-001 | Google AI Studio | $0.15 |
| gemini-embedding-001 | Vertex AI | $0.15 |
| gemini-embedding-001 | Batch API | $0.075 (50% discount) |

Free tier available for gemini-embedding-001.

### Framework Support

Google AI Python SDK (`google-generativeai`), Google Cloud Vertex AI SDK, LangChain (GoogleGenerativeAIEmbeddings, VertexAIEmbeddings), LlamaIndex. No HuggingFace/sentence-transformers/ONNX (API-only).

## 5. Code Retrieval Suitability

**Strengths:**
- **Best code retrieval scores in this evaluation** — CodeSearchNet 91.33, MTEB Code 74.66
- Dedicated `CODE_RETRIEVAL_QUERY` task type for code search optimization
- gemini-embedding-001: MRL support (128–3072 dims)
- gemini-embedding-001: 250+ languages including programming language documentation
- #1 on MTEB Multilingual leaderboard
- No infrastructure to manage — fully managed API
- Free tier for prototyping

**Weaknesses:**
- **API-only — no self-hosting possible** (vendor lock-in)
- **2,048-token context window** — shorter than many competitors (E5-mistral: 4K, GTE-Qwen2: 32K)
- Proprietary — no ability to fine-tune or customize
- $0.15/1M tokens (gemini-embedding-001) is more expensive than self-hosted alternatives at scale
- text-embedding-004 is deprecated — must migrate to gemini-embedding-001
- Dense only — no sparse retrieval for keyword matching
- Latency depends on Google Cloud availability

**Comparison to code-specialized models:**
gemini-embedding-001's CodeSearchNet score (91.33) is competitive with or exceeds dedicated code models. The `CODE_RETRIEVAL_QUERY` task type provides instruction-tuning specifically for code search. This is the strongest code retrieval evidence in the general-purpose model evaluation.

**Multi-language code support:** The 250+ language support and dedicated code task type suggest strong multi-language code retrieval, but per-language breakdowns are not available beyond CodeSearchNet's 6-language mean.

## 6. Overall Assessment

### text-embedding-004

| Field | Value |
|---|---|
| Recommendation | **Not recommended** — deprecated |
| Best use case | None — migrate to gemini-embedding-001 |

### gemini-embedding-001

| Field | Value |
|---|---|
| Recommendation | **Strong candidate** |
| Best use case | Primary code retrieval model if API dependency is acceptable; best-in-class code search with `CODE_RETRIEVAL_QUERY` task type |
| Key trade-offs | Best code retrieval scores and managed simplicity, but API-only with vendor lock-in and 2K context limit |

gemini-embedding-001 is the most compelling model in this evaluation for code retrieval, based purely on benchmark scores. Its CodeSearchNet 91.33 and MTEB Code 74.66 are the highest of any model evaluated. The `CODE_RETRIEVAL_QUERY` task type provides purpose-built code search optimization. However, the API-only deployment model creates vendor lock-in and the 2,048-token context window is a meaningful limitation for large code files. **Best used as the primary retrieval model for code search queries, paired with a self-hosted model for bulk indexing and fallback.**

The decision to use gemini-embedding-001 depends on Kenjutsu's tolerance for vendor dependency vs. the significant code retrieval quality advantage it offers.
