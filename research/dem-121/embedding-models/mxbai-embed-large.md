# mxbai-embed-large-v1

**Provider:** Mixedbread AI
**Category:** General-purpose embedding model
**Date evaluated:** 2026-03-23
**Parent issue:** DEM-123

---

## 1. Model Overview

| Field | Value |
|---|---|
| Model name | mxbai-embed-large-v1 |
| Provider | Mixedbread AI |
| Release date | March 2024 |
| Architecture | BERT-large encoder (24 blocks, 16 heads), AnglE loss training |
| Parameters | ~335M |
| Dimensions | 1024 default; Matryoshka truncation to 512 supported |
| Max context window | 512 tokens |
| License | Apache 2.0 |
| Category | General-purpose |
| HuggingFace | `mixedbread-ai/mxbai-embed-large-v1` |

Training: 700M+ contrastive pairs + 30M triplets with zero MTEB data overlap.

## 2. Benchmark Performance

### MTEB Scores (56 datasets)

| Category | Score |
|---|---|
| Overall | 64.68 |
| Retrieval (15 tasks) | 54.39 |
| Classification (12 tasks) | 75.64 |
| Clustering (11 tasks) | 46.71 |
| STS (10 tasks) | 85.00 |
| Reranking (4 tasks) | 60.11 |
| Pair Classification (3 tasks) | 87.20 |

### Code-Specific Benchmarks

None published. No code data in training corpus. Not evaluated on CodeSearchNet, CoSQA, or CoIR.

## 3. Technical Capabilities

| Capability | Status |
|---|---|
| Matryoshka (MRL) | Yes — truncation to 512 dims supported |
| Quantization | float32, int8, ubinary |
| Instruction-tuned | Yes — query-side instruction prompt required for retrieval |
| Multi-lingual | English only |
| Sparse + dense hybrid | Dense only |

Query format:
```
Represent this sentence for searching relevant passages: {query}
```

## 4. Deployment & Infrastructure

### Self-Hosted

| Precision | VRAM |
|---|---|
| FP16 | ~0.7 GB |

Runs on any GPU or CPU. Very lightweight.

### Managed API

| Provider | Price | Notes |
|---|---|---|
| Mixedbread API (fast ingestion) | $1.50/1M tokens | Platform product, not standalone embedding API |
| Mixedbread API (high quality) | $3.00/1M tokens | |
| Free tier | 2M tokens/month | |
| HuggingFace Inference API | Available | |

### Framework Support

sentence-transformers, HuggingFace Transformers, Transformers.js, ONNX, GGUF, MLX, OpenVINO, Safetensors, Infinity (Docker), Ollama, LangChain, Haystack.

Broadest framework compatibility in this evaluation.

## 5. Code Retrieval Suitability

**Strengths:**
- MRL support allows dimension flexibility
- Lightweight and easy to deploy
- Apache 2.0 license
- Broadest framework ecosystem support
- Competitive general MTEB scores for its parameter class (64.68)
- Binary quantization (ubinary) enables extremely compact storage

**Weaknesses:**
- 512-token context window is too short for code files
- No code-specific training or benchmarks
- English only
- General MTEB scores are not exceptional

**Comparison to code-specialized models:**
No code retrieval data exists. At 512 tokens and no code training, this model is not positioned for code retrieval.

**Multi-language code support:** Not applicable — English only, no code training.

## 6. Overall Assessment

| Field | Value |
|---|---|
| Recommendation | **Not recommended** |
| Best use case | General-purpose short text embedding with dimension flexibility |
| Key trade-offs | Good framework ecosystem and MRL support, but 512-token limit and no code capability make it unsuitable for Kenjutsu |

mxbai-embed-large-v1 is a solid general-purpose embedder with good ecosystem support and MRL, but the 512-token context window and absence of code-specific capability disqualify it for Kenjutsu's code retrieval use case. Its main contribution to this evaluation is demonstrating what "good general-purpose without code" looks like as a baseline.
