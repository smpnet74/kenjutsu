# OpenAI text-embedding-3-large — Embedding Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-122

---

## 1. Model Identity

| Property | Value |
|---|---|
| Full name | text-embedding-3-large |
| Organization | OpenAI |
| Release date | January 25, 2024 |
| Architecture | Proprietary (not disclosed); trained with Matryoshka Representation Learning |
| Parameters | Not disclosed |
| License | Proprietary (API access only) |

## 2. Technical Specifications

| Property | Value |
|---|---|
| Context window | 8,191 tokens |
| Default dimensions | 3,072 |
| Flexible dimensions | Any integer 1–3,072 (native Matryoshka via API `dimensions` parameter) |
| Matryoshka support | Yes — native; truncated-to-256 still outperforms ada-002 at 1,536 dims |
| Binary quantization | No native support; applied at vector DB layer (Qdrant reports 0.9966 recall with rescoring at 3,072 dims) |
| int8 quantization | No native support; post-hoc only |

## 3. Benchmark Performance

### General

| Benchmark | Score |
|---|---|
| MTEB overall | 64.6 |
| MTEB retrieval (nDCG@10) | 55.4 |
| MTEB STS | 81.7 |
| MTEB clustering | 49.0 |
| MIRACL (multilingual) | 54.9 |

### Code-Specific

| Benchmark | Score |
|---|---|
| CodeSearchNet MRR@10 (avg) | Not officially published |
| CoIR average | Not submitted |

No official code-specific benchmark scores from OpenAI. Independent comparisons consistently show it underperforming Voyage-code-3 by 5–13+ points on code retrieval tasks.

### Voyage AI Comparative Data

On Voyage's 32-dataset code evaluation suite:
- text-embedding-3-large (3072-dim): **78.48%** vs voyage-code-3 (1024-dim): **92.28%**
- text-embedding-3-large (256-dim): **83.29%** — significant degradation at low dimensions

## 4. Code Retrieval Capabilities

- **NL → code:** Moderate. Acceptable for mixed text+code RAG workloads, but clearly suboptimal for pure code search. Struggles with semantic code equivalence (different variable names, identical logic).
- **Code → code:** Moderate. No code-specific training signal; relies on general text similarity.
- **Cross-language:** Not specifically designed for cross-language code retrieval. No benchmarks available.
- **Languages supported:** General-purpose model; no explicit programming language specialization.

### Known Weaknesses for Code

- No separate query/document encoders (unlike Voyage-code-3)
- Language-agnostic tokenization misses code structure
- Common identifiers (`result`, `data`, `handler`) create semantic noise
- 8K token limit requires aggressive chunking for large files

## 5. Deployment & Cost

| Property | Value |
|---|---|
| API pricing | $0.13/1M tokens (standard); $0.065/1M tokens (batch API, 24hr SLA) |
| Self-hosted | No — API only (also available via Azure OpenAI Service) |
| GPU requirements | N/A |
| Latency | P90 ~500ms; P99 up to 5,000ms (independent benchmark from AWS us-east-1) |
| Error rate | ~0.05% |

## 6. Kenjutsu Fit (1-5)

| Criterion | Score | Notes |
|---|---|---|
| Code retrieval quality | 3 | Acceptable baseline but 13%+ behind Voyage-code-3 on code tasks |
| Context window adequacy | 3 | 8K tokens sufficient for function-level chunks; insufficient for full-file |
| Deployment flexibility | 2 | API-only; no self-hosted option |
| Cost efficiency | 4 | $0.13/1M tokens is competitive; batch API at $0.065 is attractive for indexing |
| Dimension flexibility | 4 | Full Matryoshka support (any dimension 1-3072); no native quantization |
| Ecosystem maturity | 5 | Ubiquitous; every vector DB and framework supports it |

## 7. Verdict

- **Recommendation:** **Viable alternative / Baseline comparison** — useful as the general-purpose reference point, but not recommended as primary code embedding model
- **Best use case:** Fallback or baseline for non-code content in the pipeline (documentation, issue descriptions, PR comments). Batch API pricing makes it cost-effective for indexing natural language content.
- **Key risk:** Substantially weaker on code retrieval vs. specialized models. High P99 latency (5s) makes it unsuitable for latency-sensitive real-time queries. API-only with no self-hosted escape hatch.
