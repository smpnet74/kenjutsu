# ms-marco-MiniLM Cross-Encoders — Reranking Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-124

---

## Overview

| Property | Value |
|---|---|
| Provider | Sentence-Transformers / UKP Lab (TU Darmstadt) |
| Model IDs | `cross-encoder/ms-marco-MiniLM-L-6-v2`, `cross-encoder/ms-marco-MiniLM-L-12-v2` |
| Architecture | Cross-encoder; MiniLM (distilled from BERT) |
| Training data | MS MARCO Passage Ranking dataset |
| License | Apache 2.0 |
| Release date | 2021 (v2 series) |

## Specifications

| Property | L-6-v2 | L-12-v2 |
|---|---|---|
| Layers | 6 | 12 |
| Parameters | ~22M | ~33M |
| Max input length | 512 tokens | 512 tokens |
| Input format | Query-document pair | Query-document pair |
| Output | Relevance logit (not normalized by default) | Relevance logit (not normalized by default) |

## Benchmark Performance

| Model | NDCG@10 (TREC DL 2019) | MRR@10 (MS MARCO) | Docs/sec (V100) |
|---|---|---|---|
| MiniLM-L-2-v2 | 71.01 | 34.85 | 4,100 |
| MiniLM-L-4-v2 | 73.04 | 37.70 | 2,500 |
| **MiniLM-L-6-v2** | **74.30** | **39.01** | **1,800** |
| **MiniLM-L-12-v2** | **74.31** | **39.02** | **960** |
| TinyBERT-L-2-v2 | 69.84 | 32.56 | 9,000 |

**Key finding:** L-6-v2 achieves nearly identical quality to L-12-v2 (74.30 vs. 74.31 NDCG@10) at nearly 2x the throughput (1,800 vs. 960 docs/sec). L-6-v2 is the clear efficiency sweet spot in this family.

## Code Reranking Suitability

| Criterion | Assessment |
|---|---|
| Handles code syntax | No — trained exclusively on MS MARCO (web search passages) |
| Query types tested | NL→passage (web search queries) |
| Long document handling | 512 token limit; truncates longer inputs |

**Assessment:** These are pure NL passage rerankers. They have no exposure to code syntax, variable names, or programming constructs. Transfer to code reranking is expected to be poor based on training data composition.

## Operational Characteristics

| Property | Value |
|---|---|
| Deployment | Self-hosted (open weights on HuggingFace) |
| Latency | L-6-v2: 1,800 docs/sec; L-12-v2: 960 docs/sec (V100 GPU) |
| Cost | Free (open-source); minimal infrastructure costs |
| GPU requirements | <1GB VRAM; runs on CPU (slow) or any GPU |
| Self-hosting | Trivial; sentence-transformers or HuggingFace Transformers |
| Candidate limit | Limited by GPU memory only |

## Strengths

- **Extremely lightweight** (~22-33M params) — runs anywhere, even on CPU
- Fast inference (1,800 docs/sec on V100 for L-6)
- Apache 2.0 license — fully open
- Well-established baseline; widely cited and benchmarked
- Near-identical quality between L-6 and L-12 variants
- Trivial to deploy and integrate (sentence-transformers)
- Good baseline for NL passage reranking (74.30 NDCG@10 on TREC DL19)

## Weaknesses

- **No code understanding** — trained only on web search passages
- 512-token input limit constrains code document length
- MS MARCO-only training means narrow domain coverage
- No multilingual support (English only)
- Older model (2021) — surpassed by newer rerankers on general benchmarks
- No active development or updates

## Verdict for Kenjutsu

| Criterion | Assessment |
|---|---|
| **Recommendation** | NO |
| **Best role** | Baseline/reference only; not suitable for code reranking |
| **Rationale** | MiniLM cross-encoders are excellent lightweight NL baselines but lack any code understanding. The 512-token limit and English-only, MS MARCO-only training make them unsuitable for Kenjutsu's code reranking needs. Useful only as a performance baseline to measure whether more sophisticated rerankers add value over a simple cross-encoder. |
