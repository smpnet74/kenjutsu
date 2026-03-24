# RankVicuna / RankZephyr — Reranking Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-124

---

## Overview

| Property | RankVicuna | RankZephyr |
|---|---|---|
| Provider | Castorini Group (University of Waterloo) | Castorini Group |
| Model ID | `castorini/rank_vicuna_7b_v1` | `castorini/rank_zephyr_7b_v1_full` |
| Architecture | Listwise LLM reranker; Vicuna-7B (LLaMA variant) | Listwise LLM reranker; Zephyr-7B (Mistral variant) |
| Training data | Distilled from RankGPT-3.5 outputs | Distilled from RankGPT-4 outputs with multiple reranking passes |
| License | Non-commercial (Vicuna/LLaMA restrictions) | Apache 2.0 (Mistral base) |
| Release date | 2023 | 2023-12 |

## Specifications

| Property | RankVicuna | RankZephyr |
|---|---|---|
| Parameters | 7B | 7B |
| Max input length | ~4,096 tokens (context window) | ~4,096 tokens |
| Input format | Listwise — multiple documents ranked simultaneously | Listwise — multiple documents ranked simultaneously |
| Output | Permutation of document ranks | Permutation of document ranks |
| Reranking approach | Listwise (ranks N documents at once) | Listwise (ranks N documents at once) |

### Listwise vs. Pointwise Reranking

| Aspect | Listwise (RankVicuna/RankZephyr) | Pointwise (cross-encoders, RankLLaMA) |
|---|---|---|
| Input | Query + N documents simultaneously | Query + 1 document at a time |
| Output | Ranked permutation of all N docs | Individual relevance score per doc |
| Context | Sees relative relevance across documents | Scores each document independently |
| Latency | One LLM call for N documents | N separate scoring calls |
| Scalability | Limited by context window (how many docs fit) | Scales to any number of candidates |

## Benchmark Performance

| Benchmark | RankVicuna | RankZephyr | RankGPT-4 (teacher) |
|---|---|---|---|
| TREC DL 2019 (BM25 candidates) | Competitive | **Higher** | Baseline |
| TREC DL 2020 (BM25 candidates) | Competitive | **Higher** | Baseline |
| TREC DL 2019 (ADA2 candidates) | **Higher** | Lower | — |
| TREC DL 2020 (ADA2 candidates) | **Higher** | Lower | — |
| Code-specific | Not benchmarked | Not benchmarked | — |

**Key finding:** RankZephyr matches or exceeds its RankGPT-4 teacher on several benchmarks — a strong result for a 7B distilled model. However, performance varies by first-stage retriever: RankZephyr is better with BM25 candidates, RankVicuna with dense retrieval candidates.

## Code Reranking Suitability

| Criterion | Assessment |
|---|---|
| Handles code syntax | Potentially — both base models (Vicuna/Zephyr) have some code understanding from pre-training |
| Query types tested | NL→passage (TREC DL benchmarks) |
| Long document handling | 4,096 token context; must fit query + ALL candidate documents |
| Code-specific | Not evaluated |

**Assessment:** Listwise reranking is poorly suited for code documents. The entire query plus ALL candidate documents must fit within the 4K context window. For code functions (which can be 500+ tokens each), this limits the number of candidates to ~5-7 per reranking call. Multiple sliding-window passes would be needed for larger candidate sets, increasing latency and complexity.

## Operational Characteristics

| Property | Value |
|---|---|
| Deployment | Self-hosted (HuggingFace weights); compatible with vLLM, SGLang, TensorRT-LLM |
| Latency | High — full LLM inference for each reranking call; ~1-5 seconds per call |
| Cost | Free (open-source); significant GPU infrastructure costs |
| GPU requirements | ~14GB VRAM (FP16); A100/4090 recommended |
| FlashRank integration | RankZephyr available as 4-bit GGUF (~4GB) via FlashRank |

## Strengths

- **Listwise reranking** — considers relative relevance across documents simultaneously
- RankZephyr matches/exceeds RankGPT-4 teacher quality
- Distillation from GPT-4 captures sophisticated relevance reasoning
- Compatible with optimized LLM serving (vLLM, SGLang)
- RankZephyr available as 4-bit GGUF for CPU inference via FlashRank
- Open-source with active community (Castorini's rank_llm toolkit)

## Weaknesses

- **7B parameters** — heavy for a reranking step in a real-time pipeline
- Context window limits candidates to ~5-7 code documents per call
- Listwise approach requires all candidates in a single call — poor for large candidate sets
- High latency (1-5 seconds per reranking call)
- RankVicuna limited to fixed candidate count (cannot generalize to arbitrary N)
- No code-specific training or benchmarks
- Non-commercial license for RankVicuna (Vicuna/LLaMA restrictions)
- Variable performance depending on first-stage retriever — hard to predict behavior in novel pipelines

## Verdict for Kenjutsu

| Criterion | Assessment |
|---|---|
| **Recommendation** | NO |
| **Best role** | Not suitable for real-time PR review pipeline |
| **Rationale** | Listwise LLM rerankers are architecturally mismatched for Kenjutsu's use case. The context window constraint means only 5-7 code documents can be reranked per call, and each call takes 1-5 seconds. For a PR review pipeline that needs to rerank 20-100 code chunks in real-time, the latency and context constraints are prohibitive. The listwise paradigm's advantage (seeing relative relevance) does not outweigh the practical limitations. Additionally, no code-specific training or benchmarks exist. Consider only for offline/batch reranking scenarios, not real-time PR review. |
