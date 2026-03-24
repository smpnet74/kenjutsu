# BGE-reranker-v2-m3 — Reranking Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-124

---

## Overview

| Property | Value |
|---|---|
| Provider | BAAI (Beijing Academy of Artificial Intelligence) |
| Model ID | `BAAI/bge-reranker-v2-m3` |
| Architecture | Cross-encoder; based on bge-m3 (XLM-RoBERTa variant) with LoRA fine-tuning |
| Training data | bge-m3-data, Quora, FEVER, MIRACL — multilingual retrieval datasets |
| License | Apache 2.0 |
| Release date | 2024-03-18 |

## Specifications

| Property | Value |
|---|---|
| Parameters | 568M (0.6B) |
| Max input length | 512 tokens (configurable; truncates longer inputs) |
| Input format | Query-document pair |
| Output | Raw similarity score; normalizable to [0,1] via sigmoid |
| Multi-language support | Yes — multilingual (100+ languages via XLM-RoBERTa backbone) |

## Benchmark Performance

| Benchmark | bge-reranker-v2-m3 | vs. Jina v2 (278M) | vs. mmarco-mMiniLM (118M) |
|---|---|---|---|
| BEIR (17 datasets) | **53.65** | 53.17 | 45.40 |
| MKQA (26 langs) | 54.17 | **54.83** | 53.37 |
| CodeSearchNet | 62.86 | **71.36** | 51.78 |
| ToolBench | **78.46** | 77.75 | 58.39 |
| MLDR (13 langs) | 59.73 | **68.95** | 28.91 |
| TableSearch | 74.86 | **93.31** | 53.60 |

**Key finding:** Strong general-purpose reranker with best BEIR score (53.65) among cross-encoders in this comparison. However, significantly trails Jina v2 on CodeSearchNet (62.86 vs. 71.36) and long-document tasks.

## Code Reranking Suitability

| Criterion | Assessment |
|---|---|
| Handles code syntax | Partially — CodeSearchNet score (62.86) shows reasonable but not strong transfer |
| Query types tested | NL→document (BEIR), multilingual (MIRACL, MKQA); code not a primary use case |
| Long document handling | 512 token limit is restrictive for function-length code; truncation loses context |

**Concern:** The 512-token max input length is a significant limitation for code reranking. Most meaningful code functions exceed 512 tokens when combined with the query. Truncation means the model sees incomplete code, degrading reranking quality.

## Operational Characteristics

| Property | Value |
|---|---|
| Deployment | Self-hosted (open weights on HuggingFace); no hosted API from BAAI |
| Latency | Fast inference with FP16; lightweight compared to LLM-based rerankers |
| Cost | Free (open-source); infrastructure costs only |
| GPU requirements | ~2GB VRAM (568M params, FP16); runs on consumer GPUs |
| Self-hosting | Fully supported; FlagEmbedding or HuggingFace Transformers |
| Candidate limit | Limited by GPU memory; no hard API limit |

## Strengths

- **Apache 2.0 license** — fully open for commercial use, modification, and self-hosting
- Strong general-purpose BEIR performance (53.65)
- Well-established in the community; widely integrated (Pinecone, Azure AI, LlamaIndex)
- Lightweight for self-hosting (~2GB VRAM)
- Good multilingual support
- Fine-tuning supported with documented process
- Part of the larger FlagEmbedding ecosystem (compatible embeddings + rerankers)

## Weaknesses

- **512-token max input is severely limiting** for code documents
- Trails Jina v2 significantly on code-specific benchmarks (62.86 vs. 71.36)
- Larger model (568M) than Jina v2 (278M) yet lower performance on most tasks
- No hosted API — requires self-hosting infrastructure
- 15x slower throughput than Jina v2 (per Jina's benchmarks)
- No code-specific training; code ability is pure transfer from NL

## Verdict for Kenjutsu

| Criterion | Assessment |
|---|---|
| **Recommendation** | MAYBE |
| **Best role** | Fallback/baseline reranker; strong for NL queries if code context is short |
| **Rationale** | The Apache 2.0 license and strong BEIR performance make BGE v2-m3 an excellent open-source baseline. However, the 512-token input limit is a dealbreaker for reranking function-length code. It would require chunking code into sub-512-token pieces, losing structural context. For Kenjutsu's PR review pipeline, where reranking targets are code functions, this limit is too restrictive. Consider only if paired with a chunking strategy that preserves code semantics. |
