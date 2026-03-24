# Cohere Rerank v3.5 — Reranking Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-124

---

## Overview

| Property | Value |
|---|---|
| Provider | Cohere |
| Model ID | `rerank-v3.5` |
| Architecture | Proprietary cross-encoder; transformer-based |
| Training data | Proprietary; MS MARCO + multilingual + domain-specific (finance, e-commerce, hospitality, project management, email) |
| License | Proprietary (API access only) |
| Release date | 2024-11 |

## Specifications

| Property | Value |
|---|---|
| Max input length | 4,096 tokens (query + document combined) |
| Input format | Query-document pair |
| Output | Relevance score (float, normalized) |
| Multi-language support | Yes — 100+ languages; SOTA on multilingual retrieval |
| Max documents per call | 1,000 |

## Benchmark Performance

| Benchmark | Performance |
|---|---|
| BEIR (aggregate) | SOTA claimed by Cohere (specific nDCG@10 not published) |
| Finance domain | +23.4% over Hybrid Search; +30.8% over BM25 |
| E-commerce domain | SOTA (specific scores not published) |
| Multilingual (18 langs) | SOTA on monolingual and cross-lingual settings |
| MS MARCO MRR@10 | Not publicly disclosed |
| Code-specific benchmarks | None published |

**Note:** Cohere claims SOTA on BEIR and multiple domain-specific benchmarks but does not publish granular per-dataset nDCG@10 scores, making independent verification difficult. Comparative benchmarks from Voyage AI (Sept 2024) show rerank-2 outperforming "Cohere v3" by 6.33% on average across multiple domains — though this was v3, not v3.5.

## Code Reranking Suitability

| Criterion | Assessment |
|---|---|
| Handles code syntax | No evidence of code-specific training or evaluation |
| Query types tested | NL→document (general); no NL→code or code→code benchmarks |
| Long document handling | 4,096 token context handles function-length code; sufficient for most single-function reranking |

**Key concern:** Cohere Rerank is trained on natural language domains (finance, e-commerce, etc.). There is no published evidence it handles code syntax, variable naming, or programming-language structure. Transfer from NL to code is unvalidated.

## Operational Characteristics

| Property | Value |
|---|---|
| Deployment | API-only (Cohere, AWS Bedrock, Azure AI, Oracle OCI) |
| Latency | Not publicly benchmarked; API-based (expect 50-200ms per call) |
| Cost | $2.00 per 1,000 searches (docs <500 tokens each); longer docs chunked at 500-token boundaries, each chunk counts as a search |
| GPU requirements | N/A (API-only) |
| Self-hosting | Not available (no open weights) |
| Candidate limit | 1,000 documents per reranking call |

## Strengths

- SOTA performance on general NL retrieval and multilingual reranking
- Broad language support (100+ languages)
- Large context window (4,096 tokens) — among the largest for cross-encoder rerankers
- High candidate limit (1,000 docs per call)
- Available on major cloud marketplaces (AWS Bedrock, Azure, OCI)
- Reasoning capabilities for complex queries requiring inference
- Simple API integration; no infrastructure management

## Weaknesses

- No open weights — cannot self-host or fine-tune
- No code-specific training or benchmarks; transfer to code reranking is unvalidated
- Proprietary benchmark claims without granular published scores
- Cost model penalizes long documents (>500 tokens chunked and billed separately)
- API-only deployment creates vendor lock-in and latency floor
- No published latency benchmarks

## Verdict for Kenjutsu

| Criterion | Assessment |
|---|---|
| **Recommendation** | MAYBE |
| **Best role** | Secondary/fallback reranker for NL-heavy queries (e.g., issue descriptions, commit messages) |
| **Rationale** | Industry-leading NL reranking quality, but zero evidence of code understanding. For a PR review tool where the primary reranking target is code, the lack of code-specific training or benchmarks is a significant gap. The API-only model with per-search pricing also adds cost at scale. Consider only if NL→code transfer proves adequate in spike testing. |
