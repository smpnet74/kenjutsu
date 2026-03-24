# ModernBERT-embed

**Provider:** Nomic AI (base) / LightOn (large variant)
**Category:** General-purpose embedding model (modern BERT architecture)
**Date evaluated:** 2026-03-23
**Parent issue:** DEM-123

---

## 1. Model Overview

Two variants from different fine-tuning teams, both built on the ModernBERT architecture.

| Property | modernbert-embed-base | modernbert-embed-large |
|---|---|---|
| Provider | Nomic AI | LightOn |
| Release date | Late December 2024 / Early January 2025 |
| Base model | answerdotai/ModernBERT-base | answerdotai/ModernBERT-large |
| Architecture | Encoder-only, Pre-Norm Transformer, GeGLU activations, Alternating Local/Global Attention, RoPE, Flash Attention 2 |
| Parameters | 149M | 395M |
| Dimensions | 768 | 1024 |
| Max context window | 8,192 tokens | 8,192 tokens |
| License | Apache 2.0 | Apache 2.0 |
| HuggingFace | `nomic-ai/modernbert-embed-base` | `lightonai/modernbert-embed-large` |

### Architecture Highlights

ModernBERT introduces several improvements over classic BERT:
- **Alternating Local/Global Attention:** Local 128-token sliding window with global attention every 3rd layer — reduces memory while maintaining long-range reasoning
- **GeGLU activations:** Replaces GELU for improved gradient flow
- **RoPE positional embeddings:** Enables extrapolation beyond training context
- **Unpadding:** Eliminates wasted compute on padding tokens
- **Flash Attention 2:** Hardware-optimized attention for speed
- **Pretraining on code:** 2 trillion tokens including English web, **code**, and scientific articles (3-phase: 1.7T at 1024 tokens, 250B at 8192, 50B annealing)

## 2. Benchmark Performance

### MTEB Scores (56 datasets)

| Category | Base (768d) | Base at 256d (MRL) | Large (1024d) | Large at 256d (MRL) |
|---|---|---|---|---|
| Overall | 62.62 | 61.17 | 63.84 | 62.43 |
| Retrieval (15) | 52.89 | — | 54.36 | — |
| Classification (12) | 74.31 | — | 75.03 | — |
| Clustering (11) | 44.98 | — | 46.04 | — |
| STS (10) | 81.78 | — | 83.80 | — |
| Reranking (4) | 56.42 | — | 57.64 | — |
| Pair Classification (3) | 83.96 | — | 85.31 | — |

### Code-Specific Benchmarks

| Benchmark | Score | Notes |
|---|---|---|
| StackOverflow-QA | >80 | **First model to cross 80** (backbone, not embed fine-tune) |
| CodeSearchNet (as ColBERT backbone) | State-of-the-art | Base language model, not embed fine-tune |
| CodeSearchNet (embed fine-tune) | Not published | |
| CoSQA | Not published | |
| CoIR | Not published | |

**Important distinction:** The code benchmark results are for the **raw ModernBERT base language model** used as a ColBERT backbone, not for the Nomic/LightOn embedding fine-tunes. The embed fine-tune may or may not preserve this code capability.

## 3. Technical Capabilities

| Capability | Status |
|---|---|
| Matryoshka (MRL) | Yes — 256d with ~1.4 point MTEB loss |
| Quantization | Via Transformers.js (fp32, fp16, q8, q4, q4f16) |
| Instruction-tuned | Yes — requires `search_query:` / `search_document:` prefixes |
| Multi-lingual | English only |
| Sparse + dense hybrid | Dense only (no native sparse support) |

## 4. Deployment & Infrastructure

### Self-Hosted

| Variant | VRAM (estimated) |
|---|---|
| Base (149M) | ~1–2 GB FP16 inference |
| Large (395M) | ~2–3 GB FP16 inference |

Designed for consumer GPUs (RTX 3090/4090, A10, T4, L4). Uses <1/5th DeBERTa memory. No official VRAM figures published.

### Managed API

Not deployed by any inference provider at time of evaluation. Self-hosting required.

### Framework Support

sentence-transformers, HuggingFace Transformers (>=4.48.0), Transformers.js, LangChain, LlamaIndex, Haystack. Requires Flash Attention 2 for optimal performance.

## 5. Code Retrieval Suitability

**Strengths:**
- **Pretrained on code data** — the only encoder-based model in this evaluation with code in pretraining
- ModernBERT backbone achieves >80 on StackOverflow-QA and SOTA on CodeSearchNet as ColBERT
- 8,192-token context window — handles most code files
- Lightweight (149M base, 395M large) — very efficient to deploy
- MRL support for dimension flexibility
- Apache 2.0 license
- Modern architecture with Flash Attention 2 for speed
- Unpadding eliminates waste on variable-length code inputs

**Weaknesses:**
- **Code benchmarks are for the backbone, not the embed fine-tune** — code capability may not transfer
- Overall MTEB scores are modest (62.62 / 63.84) — below many peers
- No managed API
- Relatively new — limited production track record
- English only
- Requires HF Transformers >=4.48.0 (version constraint)

**Comparison to code-specialized models:**
The ModernBERT backbone shows code-specialized-model-level performance on CodeSearchNet, but this is unverified for the embed fine-tune. If the code capability transfers, this could be competitive with code-specialized models at a fraction of the resource cost.

**Multi-language code support:** Pretrained on code (languages not specified), but the embed fine-tune may not preserve multi-language code understanding.

## 6. Overall Assessment

| Field | Value |
|---|---|
| Recommendation | **Worth considering — highest-potential sleeper candidate** |
| Best use case | Lightweight code-aware embedder if code capability transfers from backbone |
| Key trade-offs | Only encoder model pretrained on code with 8K context, but embed fine-tune code capability is unverified |

ModernBERT-embed is the most architecturally interesting model in this evaluation. It's the only encoder-based model pretrained on code data, and the backbone achieves state-of-the-art code retrieval as a ColBERT backbone. At 149M (base) or 395M (large) parameters with 8K context, it offers the best code-potential-per-VRAM ratio in the evaluation. The critical unknown is whether the Nomic/LightOn embed fine-tunes preserve the backbone's code capability — this requires running CodeSearchNet or CoIR evaluations. If code capability validates, this becomes a **strong candidate** for the indexing layer (lightweight, fast, code-aware). **Recommend local evaluation as highest priority.**
