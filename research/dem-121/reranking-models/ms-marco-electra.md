# ms-marco-ELECTRA-Base — Reranking Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-124

---

## Overview

| Property | Value |
|---|---|
| Provider | Sentence-Transformers / UKP Lab (TU Darmstadt) |
| Model ID | `cross-encoder/ms-marco-electra-base` |
| Architecture | Cross-encoder; ELECTRA-Base discriminator |
| Training data | MS MARCO Passage Ranking dataset |
| License | Apache 2.0 |
| Release date | 2021 |

## Specifications

| Property | Value |
|---|---|
| Parameters | ~110M |
| Max input length | 512 tokens |
| Input format | Query-document pair |
| Output | Relevance score [0,1] (sigmoid activation) |
| Multi-language support | No (English only) |

## Benchmark Performance

| Model | NDCG@10 (TREC DL 2019) | MRR@10 (MS MARCO) | Docs/sec (V100) |
|---|---|---|---|
| **ELECTRA-Base** | **71.99** | **36.41** | **340** |
| MiniLM-L-6-v2 | 74.30 | 39.01 | 1,800 |
| MiniLM-L-12-v2 | 74.31 | 39.02 | 960 |

**Key finding:** ELECTRA-Base is **strictly worse** than MiniLM variants on both quality metrics (71.99 vs. 74.30 NDCG@10) and throughput (340 vs. 1,800 docs/sec). It is a v1-era model that has been superseded by the v2 MiniLM family.

## Code Reranking Suitability

| Criterion | Assessment |
|---|---|
| Handles code syntax | No — trained exclusively on MS MARCO (web search passages) |
| Query types tested | NL→passage (web search queries) |
| Long document handling | 512 token limit; truncates longer inputs |

**Assessment:** Same limitations as MiniLM cross-encoders — pure NL training with no code exposure. Additionally, ELECTRA's discriminative pre-training (replaced token detection) does not offer any advantage for code understanding.

## Operational Characteristics

| Property | Value |
|---|---|
| Deployment | Self-hosted (open weights on HuggingFace) |
| Latency | 340 docs/sec (V100 GPU) — 5x slower than MiniLM-L-6-v2 |
| Cost | Free (open-source) |
| GPU requirements | ~1GB VRAM; can run on CPU (very slow) |
| Self-hosting | Supported via sentence-transformers or HuggingFace Transformers |

## Strengths

- Apache 2.0 license
- Open weights, easy to deploy
- ELECTRA architecture is parameter-efficient (discriminative, not generative)

## Weaknesses

- **Dominated by MiniLM-L-6-v2** on all metrics: lower quality AND slower inference
- No code understanding; NL-only training
- 512-token input limit
- English only
- No active development; older model superseded by v2 series
- 5x slower than MiniLM-L-6-v2 with worse quality

## Verdict for Kenjutsu

| Criterion | Assessment |
|---|---|
| **Recommendation** | STRONG NO |
| **Best role** | Not suitable for any role |
| **Rationale** | ELECTRA-Base is strictly dominated by MiniLM-L-6-v2 — it is both slower and less accurate. There is no use case where ELECTRA-Base would be preferred. For Kenjutsu, it has the additional disqualifiers of no code understanding and a 512-token limit. Skip entirely. |
