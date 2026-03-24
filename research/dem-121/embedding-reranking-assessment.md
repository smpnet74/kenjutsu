# Embedding & Reranking Assessment for Kenjutsu

> **DEM-121 Consolidated Assessment** — Synthesized from 47 individual evaluations across DEM-122, DEM-123, DEM-124, and DEM-125.
>
> **Date:** 2026-03-24 | **Author:** Chief Architect | **Status:** Final

---

## 1. Executive Summary

Kenjutsu's retrieval pipeline requires three model categories (embedding, reranking, retrieval techniques) working in concert. After evaluating **23 embedding models**, **12 reranking models**, and **12 retrieval techniques**, this assessment provides concrete recommendations for each pipeline layer.

**Top-line recommendations:**

- **Primary embedding model:** Voyage-code-3 — best-in-class code retrieval (92.28% on Voyage suite, CodeSearchNet Python 98.37 nDCG@10), 32K context, native Matryoshka + quantization
- **Self-hosted alternative:** Nomic Embed Code — near-Voyage quality, fully open (Apache 2.0), 32K context, zero vendor lock-in
- **Primary reranker:** Jina Reranker v2 — only model with published code benchmarks (CodeSearchNet 71.36), compact (278M params), fast (Flash Attention 2)
- **Complementary reranker:** Voyage Rerank 2.5 — 32K context window, cheapest API ($0.05/1M tokens), instruction-following for code-specific prompts
- **MVP retrieval stack:** Hybrid BM25 + dense retrieval, parent-child retrieval, scalar quantization, Matryoshka embeddings, code-to-NL translation before embedding

**Critical finding:** General-purpose models can match code-specialized ones — E5-mistral-7b-instruct is within 1pt of Voyage-Code-002 on CoIR; Gemini embedding-001 leads CodeSearchNet at 91.33. Model selection should not be constrained to "code-only" models.

**Key risk:** No reranker has been trained or benchmarked on code-to-code or NL-to-code reranking in a PR review context. Spike testing with Kenjutsu-specific queries against Jina v2 and Voyage Rerank is essential before committing.

---

## 2. Embedding Model Tier List

23 models evaluated across code-specialized (DEM-122: 10 models) and general-purpose (DEM-123: 13 models). Ranked by code retrieval capability, operational viability, and licensing.

### Tier 1 — Strong Recommend

| Model | Provider | Type | Dims | Context | Code Score | License | Cost/1M | MRL | Key Differentiator |
|-------|----------|------|------|---------|------------|---------|---------|-----|-------------------|
| **Voyage-code-3** | Voyage AI | Code | 1,024 (256-2,048) | 32K | 92.28% suite; CSN 98.37 | Proprietary | $0.18 | Yes | Best code retrieval, native quantization |
| **Nomic Embed Code** | Nomic AI | Code | 3,584 | 32K | CSN MRR ~82 | Apache 2.0 | ~$0.01 | No | Fully open, near-Voyage quality |
| **Gemini embedding-001** | Google | General | 3,072 (128-3,072) | 2K | CSN 91.33; MTEB Code 74.66 | Proprietary | $0.15 | Yes | `CODE_RETRIEVAL_QUERY` task type |
| **E5-mistral-7b-instruct** | Microsoft | General | 4,096 | 4K | CoIR 55.18 (rank 2/10) | MIT | ~$0.06 | No | Self-hosted, instruction-tuned |

### Tier 2 — Viable (Conditional)

| Model | Provider | Type | Dims | Context | Code Score | License | Blocker/Condition |
|-------|----------|------|------|---------|------------|---------|-------------------|
| **CodeSage-large-v2** | Amazon | Code | 2,048 | 2K | CoIR 64.18 (#2) | Apache 2.0 | 2K context limit — function-level only |
| **SFR-Embedding-Code-2B_R** | Salesforce | Code | — | ~4K | CoIR 67.41 (#1) | CC-BY-NC-4.0 | **License blocks commercial use** |
| **GTE-Qwen2-7B-instruct** | Alibaba | General | 3,584 | 32K | Not evaluated | Apache 2.0 | Must validate on code benchmarks |
| **ModernBERT-embed-large** | LightOn/Nomic | General | 1,024 | 8K | Unverified | Apache 2.0 | Must verify code capability transfers |
| **Arctic Embed v2.0** | Snowflake | General | 1,024 | 8K | Not evaluated | Apache 2.0 | Best compression; must benchmark on code |
| **Cohere embed-v4** | Cohere | General | 1,536 (256-1,536) | 128K | None published | Proprietary | 128K context unique; no code evidence |
| **OpenAI text-embedding-3-large** | OpenAI | General | 3,072 (1-3,072) | 8K | 78.48% suite | Proprietary | 13% behind Voyage; ecosystem ubiquity |

### Tier 3 — Not Recommended

| Model | Reason |
|-------|--------|
| Jina v2-base-code | Deprecated by Jina AI |
| Jina v3 | Not a code model — no code training |
| UniXcoder | 1K context, 74% MRR — obsolete |
| CodeBERT / GraphCodeBERT | 512 context, 69-71% MRR — historical baseline |
| StarEncoder | PII detection tool, not designed for retrieval |
| Stella-EN 1.5B v5 | 512 context fatal for code despite strong MTEB (71.19) |
| GTE-Qwen2-1.5B | No code evidence; defer to 7B sibling |
| BGE-M3 | Last on CoIR (39.31) despite strong general scores |
| BGE-large-en-v1.5 | 512 limit, legacy baseline |
| mxbai-embed-large-v1 | 512 limit, no code capability |
| E5-large-v2 | Superseded by E5-mistral; 512 limit |
| GTE-Large | Weakest code proxy scores (36.75) |
| NV-Embed-v2 | **CC-BY-NC license — commercial use prohibited** |
| Linq-Embed-Mistral | **CC-BY-NC license — commercial use prohibited** |

### Key Insight: MTEB ≠ Code Retrieval

General MTEB scores do not predict code retrieval performance. BGE-M3 (strong MTEB) ranked last in CoIR; E5-base-v2 (modest MTEB) ranked 3rd. **Code-specific benchmarking is the only reliable signal.**

---

## 3. Reranking Model Tier List

12 models evaluated (DEM-124). The reranking landscape for code is significantly less mature than embedding — only one model has published code benchmarks.

### Tier 1 — Strong Recommend

| Model | Provider | Params | Context | Code Score | License | Cost | Key Differentiator |
|-------|----------|--------|---------|------------|---------|------|-------------------|
| **Jina Reranker v2** | Jina AI | 278M | 1,024 (sliding) | CSN **71.36** | CC-BY-NC-4.0 | API pricing | Only reranker with code benchmarks; Flash Attention 2 |
| **Voyage Rerank 2.5** | Voyage AI | Proprietary | **32K** | Not benchmarked | Proprietary | $0.05/1M | Largest context; cheapest API; instruction-following |

### Tier 2 — Viable (Conditional)

| Model | Provider | Context | Cost | Condition |
|-------|----------|---------|------|-----------|
| **Cohere Rerank v3.5** | Cohere | 4K | $2.00/1K searches | NL queries only; zero code evidence; expensive |
| **BGE Reranker v2-m3** | BAAI | 512 | Free (Apache 2.0) | CSN 62.86 but 512-token limit severe for code |
| **FlashRank (MiniLM)** | Community | 512/8K | Free (Apache 2.0) | Prototyping baseline only |
| **ColBERT v2** | Stanford | 512 | Free (MIT) | Requires persistent index; architectural complexity |

### Tier 3 — Not Recommended

| Model | Reason |
|-------|--------|
| ms-marco-MiniLM L-6/L-12 | No code understanding, 512 limit, baseline only |
| RankLLaMA | 7B params, impractical latency for real-time use |
| RankVicuna / RankZephyr | Listwise limits to ~5-7 docs per call; 1-5s latency |
| Cross-Encoder RoBERTa-large | Strictly dominated by MiniLM in quality AND speed |
| ms-marco-ELECTRA-Base | Strictly dominated by MiniLM in quality AND speed |
| NVIDIA NV-RerankQA | Deprecated December 2025 |

### Critical Gap

No reranker has been trained or benchmarked on the specific task Kenjutsu needs: reranking code chunks in response to PR review and code search queries. Spike testing is mandatory before production commitment.

---

## 4. Retrieval Technique Recommendations

12 techniques evaluated (DEM-125), categorized by pipeline layer: MVP (deploy from day one), Layer 2 (adopt after core pipeline is stable), Layer 3 (defer to future iterations).

### MVP — Deploy from Day One

| Technique | Pipeline Stage | Why MVP | Complexity |
|-----------|---------------|---------|------------|
| **Hybrid BM25 + dense** | Retrieval | Foundational — neither BM25 nor dense alone covers both exact identifiers and semantic intent | Low-Medium |
| **Parent-child retrieval** | Retrieval + chunking | Natural fit for code — embed at function level, return class/file context. AST-defined hierarchy. | Low-Medium |
| **Scalar quantization (INT8)** | Storage | No-regret optimization — 4x storage reduction, <2% quality loss. Use as default from day one. | Low |
| **Matryoshka embeddings** | Model selection | Not a technique to add later — it's a model selection criterion. Select MRL-capable models. | Zero (model choice) |
| **Code-to-NL translation** | Indexing | +12% retrieval improvement (Greptile). Bridges NL query ↔ code vocabulary gap. | Medium |

### Layer 2 — Adopt After Core Pipeline Stable

| Technique | Pipeline Stage | When to Adopt | Complexity |
|-----------|---------------|--------------|------------|
| **Late chunking** | Indexing | After embedding model is chosen — free toggle if using Jina v3 | Low |
| **ColBERT / late interaction** | Retrieval | When single-vector retrieval quality ceiling is hit | Medium-High |
| **Binary quantization** | Storage | When index size becomes a concern (>10M vectors) | Low |
| **HyDE** | Query expansion | After benchmarking on Kenjutsu query distribution; deploy selectively for semantic queries | Medium |
| **Contextual retrieval** | Indexing | Benchmark head-to-head against code-to-NL translation; adopt winner | Medium |

### Layer 3 / Defer

| Technique | Reason to Defer |
|-----------|----------------|
| **Multi-vector representations** | No standardized approach; storage and retrieval complexity high; simpler techniques should be exhausted first |
| **Recursive retrieval / tree index** | High construction cost; code already has natural hierarchy via AST/directory structure; parent-child covers the most important 2-level case |

### Composability Notes

Several techniques are **partially redundant** — deploying both adds cost with diminishing returns:
- **Contextual retrieval vs. code-to-NL translation** — both enrich chunks with LLM-generated NL at indexing time. Head-to-head evaluation needed; adopt one.
- **Late chunking vs. contextual retrieval** — both inject document context into chunk embeddings (late chunking via attention, contextual via text prepending)
- **Parent-child retrieval vs. late chunking** — both address "chunk lacks document context"; late chunking bakes parent context into embedding, parent-child returns it at retrieval time

---

## 5. Recommended Pipeline Architecture

### Single-Model vs. Multi-Model Strategy

**Recommendation: Dual-model embedding with single reranker.**

A single embedding model cannot optimally serve all of Kenjutsu's retrieval needs. The query distribution spans:
- **NL → code** ("find the function that validates email addresses") — needs strong NL-code bridging
- **Code → code** ("find similar implementations to this function") — needs code structural understanding
- **NL → NL** ("find the PR that discussed authentication refactoring") — needs NL semantic matching

### Recommended Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                     INDEXING PIPELINE                         │
│                                                               │
│  Source Code ──► AST Chunking ──► Code-to-NL Translation     │
│                       │                    │                  │
│                       ▼                    ▼                  │
│              Function/Class         NL Summaries              │
│                 Chunks                                        │
│                       │                    │                  │
│                       ▼                    ▼                  │
│              BM25 Inverted      Dense Embedding               │
│                 Index          (Voyage-code-3 @               │
│              (code-aware         1024d + INT8)                │
│              tokenization)                                    │
│                                                               │
│  Parent Documents (class/file text) stored as metadata        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     QUERY PIPELINE                            │
│                                                               │
│  User Query ──► Query Classifier ──► Dense Embedding          │
│                       │                    │                  │
│                       ▼                    ▼                  │
│                  BM25 Search      Vector ANN Search            │
│                       │                    │                  │
│                       ▼                    ▼                  │
│                    RRF Fusion (k=60)                          │
│                         │                                     │
│                         ▼                                     │
│                   Top-k Candidates                            │
│                         │                                     │
│                         ▼                                     │
│                Jina Reranker v2                               │
│              (or Voyage Rerank 2.5                            │
│               for long documents)                             │
│                         │                                     │
│                         ▼                                     │
│              Parent-Child Expansion                           │
│           (return class/file context)                         │
│                         │                                     │
│                         ▼                                     │
│               Final Ranked Results                            │
└─────────────────────────────────────────────────────────────┘
```

### Model Selections

| Component | Primary | Fallback | Rationale |
|-----------|---------|----------|-----------|
| **Code embedding** | Voyage-code-3 (1024d, INT8) | Nomic Embed Code (self-hosted) | Best quality; fallback removes vendor dependency |
| **NL content embedding** | Same model (Voyage-code-3) | Gemini embedding-001 | Voyage handles both; Gemini for dedicated NL-code bridge if needed |
| **BM25** | Elasticsearch / Typesense | — | Code-aware tokenization (split camelCase, snake_case, dots) |
| **Reranker (short docs)** | Jina Reranker v2 | BGE Reranker v2-m3 (open-source) | Only code-benchmarked reranker |
| **Reranker (long docs)** | Voyage Rerank 2.5 (32K ctx) | — | Only reranker that handles full files without truncation |
| **Fusion** | RRF (k=60) | — | Rank-based; no score normalization needed; robust default |

### Why Not Two Embedding Models?

A dual-model strategy (e.g., Voyage for code + Gemini for NL) doubles indexing cost and index storage, and requires query routing logic. Voyage-code-3 already handles NL queries against code well (that's its primary use case). **Start with one embedding model; split only if evaluation shows significant quality gaps on specific query types.**

---

## 6. Cost-Performance Analysis

### Embedding Cost Model

Based on Voyage-code-3 at $0.18/1M tokens, with average function chunk ~200 tokens:

| Scale | Functions | Tokens | Embedding Cost | Storage (1024d INT8) | Storage (1024d binary) |
|-------|-----------|--------|---------------|---------------------|----------------------|
| Small project | 100K | 20M | **$3.60** | 100 MB | 12.5 MB |
| Medium codebase | 1M | 200M | **$36.00** | 1 GB | 125 MB |
| Large codebase | 10M | 2B | **$360.00** | 10 GB | 1.25 GB |

### Code-to-NL Translation Cost (Indexing Enrichment)

Using Claude Haiku or GPT-4o-mini (~$0.25/1M input tokens, ~$0.50/1M output tokens), ~100 output tokens per summary:

| Scale | Functions | Input Cost | Output Cost | **Total NL Cost** | Combined (Embed + NL) |
|-------|-----------|-----------|-------------|-------------------|----------------------|
| 100K | 100K | $5.00 | $5.00 | **$10.00** | **$13.60** |
| 1M | 1M | $50.00 | $50.00 | **$100.00** | **$136.00** |
| 10M | 10M | $500.00 | $500.00 | **$1,000.00** | **$1,360.00** |

### Reranking Cost (Per Query)

| Reranker | Cost per Query (top-50 rerank) | Monthly (10K queries/day) |
|----------|-------------------------------|--------------------------|
| Jina v2 API | ~$0.001-0.005 | $30-150 |
| Voyage Rerank 2.5 | ~$0.001 | $30 |
| BGE v2-m3 (self-hosted) | GPU cost only | ~$50-100/mo for a T4 |

### Total Pipeline Cost Estimate (Monthly)

| Component | 100K functions | 1M functions | 10M functions |
|-----------|---------------|-------------|--------------|
| Embedding (one-time) | $3.60 | $36 | $360 |
| Code-to-NL (one-time) | $10 | $100 | $1,000 |
| Re-indexing (10% churn/mo) | $1.36 | $13.60 | $136 |
| Reranking (10K queries/day) | $30-150 | $30-150 | $30-150 |
| Vector DB hosting | $20-50 | $50-100 | $200-500 |
| **Monthly operational** | **$50-200** | **$95-265** | **$365-785** |

### Self-Hosted Alternative

Replacing Voyage-code-3 with Nomic Embed Code (self-hosted) eliminates embedding API costs but requires GPU infrastructure:
- 1× A100 80GB: ~$1.50-2.00/hr ($1,100-1,500/mo) — handles all scales
- 1× L4 24GB: ~$0.50/hr ($365/mo) — sufficient for ≤1M functions
- Breakeven vs. Voyage API: ~$1M-2M functions for dedicated GPU

---

## 7. Multi-Model Strategy

### When to Use One Model vs. Ensemble

| Scenario | Strategy | Rationale |
|----------|----------|-----------|
| **MVP / launch** | Single model (Voyage-code-3) | Minimize complexity; Voyage handles both NL→code and code→code |
| **NL content heavy** | Add Gemini embedding-001 | If Kenjutsu indexes significant NL content (docs, issues, PRs), Gemini's `CODE_RETRIEVAL_QUERY` task type may outperform on NL→code queries |
| **Self-hosted requirement** | Replace with Nomic Embed Code | Apache 2.0, runs on single A100, near-Voyage quality |
| **Cost optimization at scale (>5M)** | Switch to self-hosted | API costs exceed GPU costs above ~2M functions |
| **Quality ceiling hit** | Add ColBERT (Layer 2) | If single-vector retrieval + reranking plateaus, ColBERT's token-level matching provides the next quality step |

### Recommended Multi-Model Decision Points

```text
MVP Launch
  └── Is retrieval quality sufficient?
       ├── YES → Stay single-model
       └── NO → Analyze failure modes
             ├── NL→code queries failing → Add Gemini as secondary
             ├── Code→code queries failing → Fine-tune or switch to Nomic
             └── Both failing → Evaluate ColBERT pipeline (Layer 2)
```

### Embedding Model for Different Content Types

| Content Type | Recommended Model | Dimension | Notes |
|-------------|-------------------|-----------|-------|
| Source code (functions/classes) | Voyage-code-3 | 1024 (INT8) | Primary use case |
| Documentation / README | Voyage-code-3 | 1024 (INT8) | Same model handles NL well |
| PR descriptions / comments | Voyage-code-3 | 1024 (INT8) | NL with code references |
| Commit messages | Voyage-code-3 | 512 (MRL truncated) | Short text; reduce dims |
| Code + NL fused chunks | Voyage-code-3 | 1024 (INT8) | Code-to-NL enriched chunks |

**A single Voyage-code-3 instance at 1024d with INT8 quantization handles all Kenjutsu content types at MVP scale.** Multi-model complexity is deferred until evaluation reveals specific gaps.

---

## 8. Migration Path

### From Current Architecture Assumptions

The existing architecture proposals (DEM-118, DEM-119, DEM-120) made preliminary model assumptions. This assessment validates and refines those choices.

| Assumption in Current Architecture | Assessment Finding | Action |
|------------------------------------|--------------------|--------|
| "Voyage-code-3 for embeddings" | **Validated** — top tier, recommended as primary | No change |
| "OpenAI text-embedding-3-large as alternative" | **Downgraded** — 13% behind Voyage on code; defer to Tier 2 | Replace with Nomic Embed Code as self-hosted alternative |
| "Jina Reranker" | **Validated** — only code-benchmarked reranker | No change, but add Voyage Rerank 2.5 as complement for long docs |
| "BM25 + dense hybrid" | **Validated** — MVP technique, foundational | No change |
| "Consider ColBERT" | **Deferred to Layer 2** — quality gain doesn't justify MVP complexity | Defer; evaluate when single-vector + reranking plateaus |

### Implementation Phases

**Phase 1: MVP Foundation (Weeks 1-4)**
1. Deploy Voyage-code-3 at 1024d with INT8 scalar quantization
2. Implement AST-aware chunking (function/class level)
3. Set up BM25 with code-aware tokenization (camelCase/snake_case splitting)
4. Implement RRF fusion (k=60) for hybrid retrieval
5. Deploy parent-child retrieval (embed functions, store class/file as parent)
6. Integrate Jina Reranker v2 for top-50 → top-10 reranking
7. Select MRL-capable model confirmed ✓ (Voyage supports Matryoshka)

**Phase 2: Enrichment (Weeks 5-8)**
1. Add code-to-NL translation at indexing time (Claude Haiku / GPT-4o-mini)
2. Evaluate: code-to-NL vs. contextual retrieval (Anthropic approach) head-to-head
3. Deploy winner as standard indexing enrichment
4. Add Voyage Rerank 2.5 for long-document reranking (>1K tokens)

**Phase 3: Optimization (Weeks 9-12)**
1. Evaluate late chunking (if Jina v3 selected, it's a free toggle)
2. Benchmark HyDE on Kenjutsu's actual query distribution
3. Implement binary quantization if index exceeds memory budget
4. Run ColBERT evaluation as next quality frontier

**Phase 4: Scale (Quarter 2)**
1. If >2M functions: evaluate self-hosted Nomic Embed Code vs. Voyage API cost
2. If quality ceiling hit: deploy ColBERT pipeline
3. If multi-content types needed: evaluate secondary model (Gemini)

---

## 9. Open Questions

### Must Resolve Before MVP

| Question | Why It Matters | Resolution Path |
|----------|---------------|-----------------|
| **Jina v2 code reranking quality in PR review context** | Only model with code benchmarks, but CodeSearchNet ≠ PR review queries | Spike test: build test set of 100 PR review queries, measure nDCG@10 |
| **Voyage-code-3 vs. Nomic Embed Code head-to-head on Kenjutsu data** | Tier 1 models within striking distance; self-hosted could save significant cost | Benchmark both on a Kenjutsu-representative code corpus |
| **Code-aware BM25 tokenization quality** | Standard BM25 mangles camelCase, snake_case, dot paths | Prototype code-aware tokenizer; evaluate on identifier-heavy queries |
| **Code-to-NL summary quality at scale** | Greptile's +12% is from a single source; LLM summaries can be wrong | Generate summaries for 1K functions; human-evaluate accuracy sample |

### Should Resolve Before Layer 2

| Question | Resolution Path |
|----------|-----------------|
| Contextual retrieval vs. code-to-NL head-to-head | Run controlled evaluation on same corpus with both approaches |
| HyDE effectiveness on code queries | Benchmark on Kenjutsu query distribution; expect inconsistent results |
| Jina Reranker v2 CC-BY-NC licensing implications | Legal review — commercial use requires Jina API; self-hosted is research-only |
| ModernBERT-embed code capability transfer | Run CoIR evaluation to verify code pretraining survives embed fine-tuning |

### Long-Term Research

| Question | Impact |
|----------|--------|
| Will code-specific ColBERT models emerge? | Could make ColBERT the clear Layer 2 upgrade — no code-specific model exists today |
| SPLADE for code — learned sparse representations | Could replace BM25 with better semantic sparse matching for code identifiers |
| Multi-modal code understanding (code + diagrams + docs) | Cohere embed-v4 (128K, multimodal) becomes interesting if Kenjutsu adds visual content |
| Codestral Embed (Mistral) | Emerging competitor to Voyage-code-3 at lower price; monitor benchmarks |

---

## Appendix A: License Risk Summary

| Model | License | Commercial Use | Risk |
|-------|---------|---------------|------|
| Voyage-code-3 | Proprietary API | Yes (API terms) | Vendor lock-in |
| Nomic Embed Code | Apache 2.0 | Yes | None |
| Gemini embedding-001 | Proprietary API | Yes (API terms) | Google API dependency |
| E5-mistral-7b-instruct | MIT | Yes | None |
| Jina Reranker v2 | CC-BY-NC-4.0 | **API only** (self-hosted = research) | Must use API for commercial |
| Voyage Rerank 2.5 | Proprietary API | Yes (API terms) | Vendor lock-in |
| SFR-Embedding-Code-2B_R | CC-BY-NC-4.0 | **No** | Hard blocker |
| NV-Embed-v2 | CC-BY-NC | **No** | Hard blocker |
| Linq-Embed-Mistral | CC-BY-NC | **No** | Hard blocker |

## Appendix B: Benchmark Reference

| Benchmark | What It Measures | Reliability |
|-----------|-----------------|-------------|
| CodeSearchNet (CSN) | NL → code retrieval across 6 languages | High — widely used, though dataset age is a concern |
| CoIR | Comprehensive code retrieval (10 subtasks) | High — standardized, multi-task, recent |
| MTEB | General embedding quality (56 tasks) | High for NL — **does not predict code performance** |
| CoSQA | Code search quality (NL→Python) | **Low — ~51% incorrect labels** (flagged in DEM-122) |
| BEIR | Information retrieval benchmark suite | High for NL domains |

## Appendix C: Individual Evaluation Index

All individual evaluations are available in subdirectories of `research/dem-121/`:

- `embedding-models/` — 23 files (10 code-specialized + 13 general-purpose)
- `reranking-models/` — 12 files
- `retrieval-techniques/` — 12 files
- `EVALUATION-FRAMEWORK.md` — standardized templates used across all evaluations
