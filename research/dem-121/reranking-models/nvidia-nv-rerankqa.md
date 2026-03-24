# NVIDIA NV-RerankQA-Mistral-4B-v3 — Reranking Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-124

---

## Overview

| Property | Value |
|---|---|
| Provider | NVIDIA (NeMo Retriever) |
| Model ID | `nvidia/nv-rerankqa-mistral-4b-v3` |
| Architecture | Transformer encoder; Mistral-7B-v0.1 truncated to first 16 layers with binary classification head |
| Training data | QA-focused ranking datasets; specifics not publicly disclosed |
| License | NVIDIA AI Foundation Models Community License + Apache 2.0 |
| Release date | 2024 (deprecated 2025-12-19) |

## Specifications

| Property | Value |
|---|---|
| Parameters | ~4B (first 16 of 32 Mistral layers) |
| Max input length | 512 tokens (query + passage combined) |
| Input format | Query-passage pair |
| Output | Relevance logit score |
| Multi-language support | Yes — multilingual |
| Max passages per call | 512 |

## Benchmark Performance

| Benchmark | Metric | Performance |
|---|---|---|
| NQ (Natural Questions) | Recall@5 | Evaluated (specific scores behind NIM docs) |
| HotpotQA | Recall@5 | Evaluated |
| FiQA (Finance QA) | Recall@5 | Evaluated |
| TechQA | Recall@5 | Evaluated |
| Code-specific | — | Not benchmarked |

**Note:** NVIDIA reports benchmark performance through their NIM documentation but does not publish detailed comparison tables publicly. Average latency reported as ~266ms per scoring call.

## Code Reranking Suitability

| Criterion | Assessment |
|---|---|
| Handles code syntax | Unknown — Mistral base has code understanding, but reranker fine-tuning focused on QA |
| Query types tested | NL→passage (QA-focused benchmarks) |
| Long document handling | 512 token limit is restrictive for code documents |

**Assessment:** The model name ("RerankQA") signals it was optimized for question-answering retrieval, not code search. While the Mistral base model has code understanding, the QA-focused fine-tuning likely does not preserve it for reranking. The 512-token limit further constrains its utility for code.

## Operational Characteristics

| Property | Value |
|---|---|
| Deployment | Self-hosted via NVIDIA NIM (Docker); previously available as hosted API (deprecated) |
| Latency | ~266ms average per scoring call |
| Cost | Free for self-hosting (NIM container); previously available via NVIDIA API credits |
| GPU requirements | Significant — 4B parameter model; likely requires 8-16GB VRAM |
| Self-hosting | Docker-based NIM microservice; GPU required |

## Strengths

- Innovative architecture — using only first 16 of 32 Mistral layers for speed
- Part of NVIDIA NeMo Retriever ecosystem with enterprise support
- Multilingual capability from Mistral backbone
- Docker-based deployment via NIM is well-supported

## Weaknesses

- **DEPRECATED as of December 2025** — no longer actively maintained
- 512-token input limit constrains code document length
- QA-focused training; not designed for code reranking
- 4B parameters is heavy for a reranker with 512-token limit
- ~266ms latency is slow compared to cross-encoders (MiniLM: <1ms/doc)
- Benchmark scores not transparently published
- Requires NVIDIA GPU ecosystem (NIM, Docker)
- Superseded by `llama-3.2-nv-rerankqa-1b-v2` (smaller, maintained)

## Verdict for Kenjutsu

| Criterion | Assessment |
|---|---|
| **Recommendation** | STRONG NO |
| **Best role** | Not suitable — deprecated model |
| **Rationale** | NV-RerankQA-Mistral-4B-v3 was deprecated in December 2025. It is no longer maintained and has been superseded by newer NVIDIA models. Even before deprecation, its 512-token limit, QA-only focus, high latency (266ms), and 4B parameter overhead made it a poor fit for Kenjutsu's code reranking needs. Do not adopt a deprecated model for a new pipeline. |
