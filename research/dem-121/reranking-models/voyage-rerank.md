# Voyage Rerank — Reranking Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-124

---

## Overview

| Property | Value |
|---|---|
| Provider | Voyage AI (acquired by Anthropic, 2025) |
| Model IDs | `rerank-2` (current), `rerank-2-lite` (lighter), `rerank-2.5` (latest, Aug 2025), `rerank-2.5-lite` |
| Architecture | Proprietary cross-encoder |
| Training data | Proprietary; multilingual + multi-domain |
| License | Proprietary (API access only) |
| Release date | rerank-2: 2024-09; rerank-2.5: 2025-08 |

## Specifications

| Property | rerank-2 | rerank-2.5 |
|---|---|---|
| Max input length | 16,000 tokens | 32,000 tokens |
| Max query length | 4,000 tokens | Not specified |
| Input format | Query-document pair | Query-document pair (instruction-following) |
| Output | Relevance score | Relevance score |
| Multi-language support | Yes — multilingual | Yes — multilingual |
| Max documents per call | 1,000 | 1,000 |
| Total token limit | Not specified | 600,000 tokens per request |

## Benchmark Performance

### rerank-2 vs. Competitors (Voyage AI benchmarks, Sept 2024)

| Comparison | Avg. improvement |
|---|---|
| rerank-2 vs. rerank-1 | +2.84% |
| rerank-2 vs. Cohere v3 | +6.33% |
| rerank-2 vs. BGE v2-m3 | +14.75% |
| rerank-2 vs. OpenAI v3 large (embedding) | +13.89% |

### Multilingual Performance

| Comparison | Avg. improvement |
|---|---|
| rerank-2 vs. rerank-1 | +1.62% |
| rerank-2 vs. Cohere multilingual v3 | +8.83% |
| rerank-2 vs. BGE v2-m3 | +4.86% |

**Note:** These are Voyage AI's own benchmarks. Independent third-party verification is limited. The comparison is against Cohere v3 (not v3.5) and older BGE versions.

### Code-Specific Performance

No published code-specific benchmarks (CodeSearchNet, code retrieval, etc.).

## Code Reranking Suitability

| Criterion | Assessment |
|---|---|
| Handles code syntax | Unknown — no code-specific benchmarks published |
| Query types tested | NL→document (general retrieval, multilingual) |
| Long document handling | **Excellent** — 16K (rerank-2) to 32K (rerank-2.5) token context handles entire files |

**Assessment:** Voyage rerankers have the largest context windows among all evaluated models (16K-32K tokens). This is a significant advantage for code reranking where functions can be long. However, there is no evidence the models understand code syntax — code reranking ability relies on NL transfer.

## Operational Characteristics

| Property | Value |
|---|---|
| Deployment | API-only (Voyage AI, AWS Marketplace) |
| Latency | Not publicly benchmarked |
| Cost | $0.05 per 1M tokens; first 200M tokens free |
| GPU requirements | N/A (API-only) |
| Self-hosting | Not available (no open weights) |
| Candidate limit | 1,000 documents per call; 600K total tokens per request (rerank-2.5) |

## Strengths

- **Largest context window** among evaluated rerankers (32K tokens for rerank-2.5) — can rerank entire files
- Very competitive pricing ($0.05/1M tokens — 40x cheaper than Cohere per token)
- Strong general retrieval performance; outperforms Cohere v3 and BGE on Voyage's benchmarks
- rerank-2.5 adds **instruction-following** — custom reranking criteria
- High candidate limit (1,000 docs)
- Free tier (200M tokens) for evaluation
- Anthropic acquisition (2025) suggests long-term stability and potential integration synergies

## Weaknesses

- No open weights — API-only, cannot self-host
- No code-specific benchmarks or training
- Benchmark claims are self-reported; compared against older Cohere v3, not v3.5
- API-only creates vendor dependency (though Anthropic ownership may align with Kenjutsu stack)
- Latency not publicly documented
- Newer rerank-2.5 has limited production track record

## Verdict for Kenjutsu

| Criterion | Assessment |
|---|---|
| **Recommendation** | YES |
| **Best role** | Primary API-based reranker candidate; strong value for long code documents |
| **Rationale** | Voyage Rerank's 32K token context window is uniquely suited for reranking function-length and file-length code documents without truncation. The pricing ($0.05/1M tokens) is significantly cheaper than Cohere ($2/1K searches). The instruction-following capability in rerank-2.5 could enable code-specific reranking prompts (e.g., "rank by relevance to this code review query"). The lack of code-specific benchmarks is a risk, but the long context window and instruction-following capability provide a credible path to code reranking. Spike testing against code retrieval tasks is recommended. Anthropic ownership is a strategic alignment factor. |
