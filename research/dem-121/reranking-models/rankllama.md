# RankLLaMA — Reranking Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-124

---

## Overview

| Property | Value |
|---|---|
| Provider | Castorini Group (University of Waterloo) |
| Model ID | `castorini/rankllama-v1-7b-lora-passage` (passage), `castorini/rankllama-v1-7b-lora-doc` (document) |
| Architecture | LLM-based pointwise reranker; LLaMA-2-7B with LoRA fine-tuning |
| Training data | MS MARCO Passage Ranking (passage variant); MS MARCO Document Ranking (document variant) |
| License | Llama 2 Community License |
| Release date | 2023-10 |

## Specifications

| Property | Passage variant | Document variant |
|---|---|---|
| Parameters | 7B (base) + LoRA adapters | 7B (base) + LoRA adapters |
| Max input length | ~512 tokens (passage) | 4,096 tokens (document) |
| Input format | `query: {q}` + `document: {title} {passage}` | Same format, longer context |
| Output | Single logit score (relevance) | Single logit score |
| Reranking approach | Pointwise (scores each query-doc pair independently) | Pointwise |

## Benchmark Performance

| Benchmark | RankLLaMA 7B | Notes |
|---|---|---|
| TREC DL 2019 nDCG@10 | 76.8 | Strong; competitive with larger models |
| MS MARCO MRR@10 | Not published on model card | Refer to paper arXiv:2310.08319 |
| BEIR (zero-shot) | Not benchmarked on model card | Paper evaluates on selected BEIR tasks |
| Code-specific | None | Not evaluated on code retrieval tasks |

**Key finding:** RankLLaMA achieves strong TREC DL19 performance (76.8 nDCG@10) — notably higher than cross-encoder baselines like MiniLM (74.30). However, it does so at orders of magnitude higher compute cost (7B params vs. 22M).

## Code Reranking Suitability

| Criterion | Assessment |
|---|---|
| Handles code syntax | Potentially — LLaMA-2's pre-training included code, but reranker fine-tuning was NL-only (MS MARCO) |
| Query types tested | NL→passage, NL→document |
| Long document handling | Document variant supports 4,096 tokens — adequate for function-length code |

**Assessment:** LLaMA-2's base model has some code understanding from pre-training, which may transfer to reranking. However, the LoRA fine-tuning was exclusively on MS MARCO (NL web passages), so code reranking ability is speculative and unvalidated.

## Operational Characteristics

| Property | Value |
|---|---|
| Deployment | Self-hosted only (HuggingFace weights) |
| Latency | High — 7B parameter model; requires GPU inference; ~10-50ms per query-doc pair on A100 |
| Cost | Free (open-source); significant GPU infrastructure costs |
| GPU requirements | ~14GB VRAM (FP16) for inference; A100/4090 recommended |
| Self-hosting | Requires PEFT + Transformers; merge LoRA adapters before deployment |
| Candidate limit | Practical limit ~50-100 candidates per query due to latency |

## Strengths

- Higher quality than cross-encoder baselines on TREC DL19 (76.8 vs. 74.3)
- LLaMA-2 base may provide some code understanding via pre-training
- Document variant supports 4,096 tokens — good for longer code
- Open weights (Llama 2 license)
- Part of Castorini's well-maintained rank_llm ecosystem
- Pointwise scoring is simpler to integrate than listwise approaches

## Weaknesses

- **7B parameters** — orders of magnitude more compute than cross-encoders for marginal quality gains
- High latency per query-doc pair; impractical for reranking >100 candidates
- Requires significant GPU infrastructure (14GB+ VRAM)
- MS MARCO-only fine-tuning; no code-specific training
- LoRA adapters need merging for efficient inference
- Not compatible with quantization without quality degradation (per search results)
- Older LLaMA-2 base — newer models (LLaMA-3) offer better base capabilities

## Verdict for Kenjutsu

| Criterion | Assessment |
|---|---|
| **Recommendation** | NO |
| **Best role** | Not suitable — too heavy for real-time PR review pipeline |
| **Rationale** | RankLLaMA's 7B parameter footprint makes it impractical for Kenjutsu's real-time PR review pipeline, where reranking latency directly impacts user experience. The marginal quality improvement over cross-encoders (~2.5 NDCG@10 points) does not justify 100x+ compute cost. No code-specific training or benchmarks. Consider only if all lightweight alternatives prove inadequate AND latency budget allows 500ms+ reranking. |
