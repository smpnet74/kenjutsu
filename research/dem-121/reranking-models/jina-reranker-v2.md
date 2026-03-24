# Jina Reranker v2 — Reranking Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-124

---

## Overview

| Property | Value |
|---|---|
| Provider | Jina AI |
| Model ID | `jinaai/jina-reranker-v2-base-multilingual` |
| Architecture | Cross-encoder; XLM-RoBERTa variant with Flash Attention 2 |
| Training data | Large-scale query-document pairs; 4-stage progressive training (English → cross-lingual → multilingual → hard negatives) |
| License | CC-BY-NC-4.0 (research/evaluation); commercial use via Jina AI APIs or marketplace |
| Release date | 2024-06 |

## Specifications

| Property | Value |
|---|---|
| Parameters | 278M |
| Max input length | 1,024 tokens (sliding window for longer documents) |
| Input format | Query-document pair |
| Output | Relevance score (float) |
| Multi-language support | Yes — 100+ languages |

## Benchmark Performance

| Benchmark | jina-reranker-v2 (278M) | bge-reranker-v2-m3 (568M) | mmarco-mMiniLMv2 (118M) |
|---|---|---|---|
| MKQA (26 langs) | **54.83** | 54.17 | 53.37 |
| BEIR (17 datasets) | 53.17 | **53.65** | 45.40 |
| MLDR (13 langs) | **68.95** | 59.73 | 28.91 |
| CodeSearchNet | **71.36** | 62.86 | 51.78 |
| AirBench | **61.33** | 61.28 | 56.46 |
| ToolBench | 77.75 | **78.46** | 58.39 |
| TableSearch | **93.31** | 74.86 | 53.60 |

**Key finding:** Jina Reranker v2 scores **71.36 on CodeSearchNet** — significantly ahead of BGE-reranker-v2-m3 (62.86) and the MiniLM baseline (51.78). This is the strongest code-specific reranking benchmark result among the models evaluated.

## Code Reranking Suitability

| Criterion | Assessment |
|---|---|
| Handles code syntax | Yes — explicitly benchmarked on CodeSearchNet with strong results |
| Query types tested | NL→code (CodeSearchNet), function calling (ToolBench), structured data (TableSearch, SQL) |
| Long document handling | 1,024 token base window with automatic sliding-window chunking for longer inputs |

**Standout:** Jina v2 is one of the few rerankers with **published code search benchmarks**. The 71.36 CodeSearchNet score and function-calling awareness (ToolBench) suggest genuine code understanding, not just NL transfer.

## Operational Characteristics

| Property | Value |
|---|---|
| Deployment | API (Jina AI), self-hosted (HuggingFace weights for research), AWS SageMaker, Azure Marketplace |
| Latency | 15x faster throughput than bge-reranker-v2-m3; Flash Attention 2 enables 3-6x speedup |
| Cost | API pricing via Jina AI (not publicly listed per-token); free for research use |
| GPU requirements | Runs on consumer GPUs for research (278M params, BF16); ~1GB VRAM |
| Candidate limit | Not explicitly documented; API may have limits |

## Strengths

- **Strongest code reranking benchmark** among evaluated models (CodeSearchNet 71.36)
- Small model size (278M) with competitive or superior performance vs. larger models (568M BGE)
- Flash Attention 2 for fast inference
- Function-calling and structured data awareness (ToolBench, TableSearch)
- Excellent multilingual performance (MKQA, MLDR)
- Sliding window handles documents >1,024 tokens
- Open weights available for research/evaluation

## Weaknesses

- CC-BY-NC-4.0 license restricts commercial self-hosting (must use Jina APIs for production)
- 1,024 token base window is relatively short; sliding window adds latency for long documents
- Less established benchmark track record than Cohere on general NL tasks
- API pricing not transparently published
- Newer model with less production deployment track record

## Verdict for Kenjutsu

| Criterion | Assessment |
|---|---|
| **Recommendation** | STRONG YES |
| **Best role** | Primary reranker candidate — strongest code-specific evidence |
| **Rationale** | The only reranker in this evaluation with strong, published code search benchmarks (CodeSearchNet 71.36). Combined with function-calling awareness, fast inference via Flash Attention, and a compact 278M parameter footprint, Jina v2 is the most evidence-backed choice for code reranking. The CC-BY-NC-4.0 license means production deployment requires Jina APIs, but the quality-to-size ratio is compelling. Must validate licensing terms for Kenjutsu's deployment model. |
