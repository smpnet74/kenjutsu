# FlashRank — Reranking Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-124

---

## Overview

| Property | Value |
|---|---|
| Provider | Prithivi Da (open-source community) |
| Model ID | `prithivida/flashrank` (library); wraps multiple backend models |
| Architecture | Library/framework — supports cross-encoder (ONNX) and listwise LLM (GGUF) backends |
| Training data | N/A (uses pre-trained models; default is ms-marco-TinyBERT-L-2-v2) |
| License | Apache 2.0 |
| Release date | 2024 (latest v0.2.10, Jan 2025) |

## Specifications

| Property | Value |
|---|---|
| Default model size | ~4MB (ms-marco-TinyBERT-L-2-v2) |
| Largest cross-encoder | ~150MB (ms-marco-MultiBERT-L-12) |
| LLM backend | ~4GB (rank_zephyr_7b_v1_full, 4-bit GGUF) |
| Max input length | 512 tokens (cross-encoder); 8,192 tokens (LLM-based) |
| Input format | Query + list of documents |
| Dependencies | No Torch/Transformers required — uses ONNX Runtime |

### Supported Models

| Model | Size | Type | Notes |
|---|---|---|---|
| ms-marco-TinyBERT-L-2-v2 | ~4MB | Cross-encoder | Default; tiniest reranker |
| ms-marco-MiniLM-L-12-v2 | ~34MB | Cross-encoder | Best quality CE |
| rank-T5-flan | ~110MB | Seq2seq | Best non-CE reranker |
| ms-marco-MultiBERT-L-12 | ~150MB | Cross-encoder | 100+ languages |
| ce-esci-MiniLM-L12-v2 | — | Cross-encoder | E-commerce focused |
| rank_zephyr_7b_v1_full | ~4GB | LLM (GGUF) | Listwise; highest quality |

## Benchmark Performance

FlashRank wraps existing models, so benchmark performance depends on the backend model selected:

| Backend Model | NDCG@10 (TREC DL19) | MRR@10 (MS MARCO) | Throughput |
|---|---|---|---|
| TinyBERT-L-2-v2 (default) | 69.84 | 32.56 | Very fast (CPU) |
| MiniLM-L-12-v2 | 74.31 | 39.02 | Fast (CPU) |
| rank_zephyr_7b (GGUF) | ~76+ (estimated) | — | Slow (CPU/GPU) |

**Key finding:** FlashRank's value is not in model quality (it wraps existing models) but in **deployment simplicity**: ONNX runtime, no Torch dependency, CPU-only operation.

## Code Reranking Suitability

| Criterion | Assessment |
|---|---|
| Handles code syntax | Depends on backend; default TinyBERT has no code understanding |
| Query types tested | NL→passage (MS MARCO); no code-specific evaluation |
| Long document handling | 512 tokens for CE backends; 8,192 for LLM backend |

## Operational Characteristics

| Property | Value |
|---|---|
| Deployment | Self-hosted; Python library (pip install flashrank) |
| Latency | Very fast on CPU (ONNX Runtime); no GPU required for CE models |
| Cost | Free (open-source) |
| GPU requirements | None for cross-encoder models; optional for LLM backend |
| Dependencies | Minimal — no PyTorch, no Transformers; ONNX Runtime only |
| Integration | Simple Python API; compatible with LlamaIndex, LangChain |

## Strengths

- **Ultra-lightweight deployment** — 4MB default model, CPU-only, no Torch dependency
- Apache 2.0 license
- Multiple backend models for different quality/speed trade-offs
- ONNX runtime for fast, portable inference
- Zero infrastructure complexity — `pip install flashrank` and go
- Supports both pairwise (cross-encoder) and listwise (LLM) reranking
- Multilingual option (MultiBERT backend)

## Weaknesses

- Not a model — a wrapper library; quality limited by underlying models
- Default model (TinyBERT-L-2) has lowest quality among all evaluated rerankers
- No code-specific models or benchmarks
- LLM backend (GGUF) adds significant size and latency
- Limited community; single-maintainer project
- No hosted API option
- Models are all MS MARCO-trained; no code or domain-specific fine-tuning

## Verdict for Kenjutsu

| Criterion | Assessment |
|---|---|
| **Recommendation** | MAYBE |
| **Best role** | Lightweight baseline reranker for prototyping; potential production use with MiniLM-L-12 backend |
| **Rationale** | FlashRank's value proposition is deployment simplicity, not model quality. For Kenjutsu's prototyping phase, FlashRank with the MiniLM-L-12 backend provides a zero-infrastructure baseline reranker that "just works" on CPU. This is useful for validating the reranking stage of the pipeline before committing to a more sophisticated (and more complex) model. Not recommended as the production reranker due to the underlying models' lack of code understanding. |
