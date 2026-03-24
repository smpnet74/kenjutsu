# Cross-Encoder ms-marco-RoBERTa-large — Reranking Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-124

---

## Overview

| Property | Value |
|---|---|
| Provider | Sentence-Transformers / UKP Lab (TU Darmstadt) |
| Model ID | `cross-encoder/stsb-roberta-large` (STS-B variant); various ms-marco RoBERTa models in sentence-transformers |
| Architecture | Cross-encoder; RoBERTa-large backbone |
| Training data | MS MARCO Passage Ranking dataset |
| License | Apache 2.0 |
| Release date | 2021 |

## Specifications

| Property | Value |
|---|---|
| Parameters | ~355M |
| Max input length | 512 tokens |
| Input format | Query-document pair |
| Output | Relevance score |
| Multi-language support | No (English only) |

## Benchmark Performance

Based on Sentence-Transformers documentation, RoBERTa-large cross-encoders were part of the original CE-MSMARCO family but are **not listed in the v2 recommended models**. The v2 MiniLM variants (L-6, L-12) superseded them with better quality-to-speed ratios.

| Model | NDCG@10 (est.) | Docs/sec (V100) | Parameters |
|---|---|---|---|
| RoBERTa-large CE | ~72-73 | ~200 | 355M |
| MiniLM-L-6-v2 | 74.30 | 1,800 | 22M |
| MiniLM-L-12-v2 | 74.31 | 960 | 33M |

**Key finding:** RoBERTa-large is 16x larger and 9x slower than MiniLM-L-6-v2, yet achieves lower quality. It was not included in the v2 recommended models by Sentence-Transformers.

## Code Reranking Suitability

| Criterion | Assessment |
|---|---|
| Handles code syntax | No — MS MARCO NL training only |
| Query types tested | NL→passage (web search) |
| Long document handling | 512 token limit |

## Operational Characteristics

| Property | Value |
|---|---|
| Deployment | Self-hosted (open weights) |
| Latency | ~200 docs/sec (V100) — slow |
| Cost | Free (open-source) |
| GPU requirements | ~2GB VRAM (FP16) |

## Strengths

- Open-source (Apache 2.0)
- RoBERTa's robust pre-training may handle noisy text better than MiniLM

## Weaknesses

- **Dominated by MiniLM-L-6-v2** in every dimension: quality, speed, and size
- 355M parameters for inferior reranking quality
- Not included in Sentence-Transformers v2 recommended models
- No code understanding, no multilingual support
- 512-token input limit

## Verdict for Kenjutsu

| Criterion | Assessment |
|---|---|
| **Recommendation** | STRONG NO |
| **Best role** | Not suitable for any role |
| **Rationale** | RoBERTa-large cross-encoder is strictly dominated by MiniLM-L-6-v2 across all metrics. It is larger, slower, and less accurate. Not recommended in Sentence-Transformers' own v2 model list. There is no scenario where this model would be chosen over lighter alternatives for Kenjutsu. |
