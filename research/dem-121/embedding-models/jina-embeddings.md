# Jina Embeddings (v2-base-code / v3) — Embedding Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-122

---

This evaluation covers two Jina AI models: the code-specialized **jina-embeddings-v2-base-code** and the general-purpose **jina-embeddings-v3**. Jina has since released dedicated code successors (jina-code-embeddings-0.5b/1.5b), which are noted but not the focus of DEM-122.

---

## Model A: jina-embeddings-v2-base-code

### 1. Model Identity

| Property | Value |
|---|---|
| Full name | jina-embeddings-v2-base-code |
| Organization | Jina AI |
| Release date | February 5, 2024 |
| Architecture | JinaBERT (BERT-based) with symmetric bidirectional ALiBi |
| Parameters | 161M (307 MB fp32) |
| License | Apache 2.0 |
| **Status** | **Deprecated** — Jina recommends jina-code-embeddings-1.5b as successor |

### 2. Technical Specifications

| Property | Value |
|---|---|
| Context window | 8,192 tokens (trained at 512, extrapolates via ALiBi) |
| Default dimensions | 768 (fixed) |
| Flexible dimensions | No |
| Matryoshka support | No |
| Binary quantization | No native support |
| int8 quantization | No native support |
| Late chunking | Yes — API supports `late_chunking=True` |

### 3. Benchmark Performance

#### Code-Specific

| Benchmark | Score |
|---|---|
| COIR-CodeSearchNet | 86.45% |
| Doc2Code | 96.34% |
| CodeTransOceanContest (code→code) | 92.54% |
| CoSQA nDCG@10 | 0.41 ⚠️ **UNRELIABLE** |

Led 9 of 15 CodeNetSearch benchmarks at release.

#### CoSQA Benchmark Warning

CoSQA has approximately **51% incorrect labels** due to a source mismatch (Bing search queries paired with CodeSearchNet code). The 0.41 nDCG@10 score — while higher than competitors — is not meaningful for model differentiation. CoSQA+ (412K pairs, 1K human-verified) is the recommended replacement benchmark.

### 4. Code Retrieval Capabilities

- **NL → code:** Good at release; led on multiple CodeSearchNet benchmarks
- **Code → code:** Good (92.54% on CodeTransOceanContest)
- **Cross-language:** Supported via training on 30 programming languages
- **Languages supported:** 30 programming languages (Python, JavaScript, Java, PHP, Go, Ruby, C, C++, C#, Rust, TypeScript, and 19 others)

### 5. Deployment & Cost

| Property | Value |
|---|---|
| API pricing | ~$0.02–$0.05/1M tokens (historical; model deprecated from API) |
| Self-hosted | Yes — Apache 2.0, weights on HuggingFace, Ollama community support |
| GPU requirements | Small (161M params); runs on CPU or consumer GPU |
| Latency | API: worst-in-class P90 among major providers; 1.45% error rate (independent benchmark). Self-hosted: fast due to small model size. |

---

## Model B: jina-embeddings-v3

### 1. Model Identity

| Property | Value |
|---|---|
| Full name | jina-embeddings-v3 |
| Organization | Jina AI |
| Release date | September 18, 2024 |
| Architecture | jina-XLM-RoBERTa (24 layers) + 5 task-specific LoRA adapters |
| Parameters | 570M |
| License | Verify on HuggingFace model card (v2 was Apache 2.0) |

### 2. Technical Specifications

| Property | Value |
|---|---|
| Context window | 8,192 tokens |
| Default dimensions | 1,024 |
| Flexible dimensions | Down to 32 via Matryoshka |
| Matryoshka support | Yes — MRL, truncatable from 1,024 to 32 |
| Binary quantization | Yes — post-hoc (up to 256x combined with MRL) |
| int8 quantization | Yes — post-hoc |
| Late chunking | Yes — first-class API support |

### Task LoRA Adapters

| Adapter | Use Case |
|---|---|
| `retrieval.query` | Asymmetric query encoding |
| `retrieval.passage` | Asymmetric document encoding |
| `separation` | Clustering |
| `classification` | Classification |
| `text-matching` | Semantic similarity |

### 3. Benchmark Performance

#### General

| Benchmark | Score |
|---|---|
| MTEB overall | 65.52 |
| MTEB classification | 82.58 |
| MTEB STS | 85.80 |

Ranked #2 on MTEB English for models under 1B parameters at release. Outperforms OpenAI text-embedding-3-large on English MTEB.

#### Code-Specific

**Not a code model.** Jina does not report code retrieval benchmarks for v3. It is designed for multilingual text across 108 human languages, not programming languages.

### 4. Code Retrieval Capabilities

- **NL → code:** Not designed for this; no code-specific training
- **Code → code:** Not designed for this
- **Cross-language:** Excellent for human languages (108); not for programming languages
- **Languages supported:** 108 human languages; no programming language specialization

### 5. Deployment & Cost

| Property | Value |
|---|---|
| API pricing | ~$0.02–$0.05/1M tokens (Jina does not publish public rates as of March 2026) |
| Free tier | 10M tokens for new users |
| Self-hosted | Yes — weights on HuggingFace |
| GPU requirements | Moderate (570M params) |
| Latency | API: worst-in-class P90 in independent benchmark; self-hosted ONNX optimized |

---

## Comparison Table

| Property | v2-base-code | v3 |
|---|---|---|
| Purpose | Code specialist | General multilingual |
| Parameters | 161M | 570M |
| Context window | 8,192 | 8,192 |
| Dimensions | 768 (fixed) | 1,024 (MRL to 32) |
| Matryoshka | No | Yes |
| Late chunking | Yes | Yes |
| Code benchmarks | Good (9/15 CSN leads) | Not applicable |
| MTEB overall | Not submitted | 65.52 |
| Open source | Yes (Apache 2.0) | Yes (verify license) |
| Status | **Deprecated** | Active |

---

## Kenjutsu Fit (1-5)

### v2-base-code

| Criterion | Score | Notes |
|---|---|---|
| Code retrieval quality | 3 | Good at release but now superseded; deprecated |
| Context window adequacy | 4 | 8K sufficient for function-level chunks |
| Deployment flexibility | 5 | Fully open-source, lightweight, runs anywhere |
| Cost efficiency | 5 | Free to self-host; 161M params is very cheap |
| Dimension flexibility | 1 | Fixed 768-dim, no Matryoshka, no native quantization |
| Ecosystem maturity | 2 | Deprecated; successor models exist |

### v3

| Criterion | Score | Notes |
|---|---|---|
| Code retrieval quality | 2 | Not a code model; no code-specific training |
| Context window adequacy | 4 | 8K sufficient |
| Deployment flexibility | 4 | Open weights + API; good flexibility |
| Cost efficiency | 4 | Moderate; 570M is efficient |
| Dimension flexibility | 5 | Excellent MRL (1024→32) + post-hoc quantization |
| Ecosystem maturity | 4 | Active development; good integrations |

## Verdict

### v2-base-code
- **Recommendation:** **Not recommended** — deprecated model with no future updates
- **Best use case:** Historical reference only. If needing a Jina code model, use jina-code-embeddings-1.5b (MTEB Code AVG: 78.94%).
- **Key risk:** Deprecated; no further updates or support. CoSQA benchmark claims are unreliable.

### v3
- **Recommendation:** **Not recommended for code** — excellent general-purpose model but lacks code specialization
- **Best use case:** Could serve as the natural language embedding model for non-code content (documentation, PR descriptions, issue text) if Kenjutsu adopts a multi-model strategy.
- **Key risk:** Using a non-code model for code retrieval would underperform specialized alternatives by a significant margin.

### Note on Jina Code Successors

Jina has released **jina-code-embeddings-0.5b** (MTEB Code AVG: 78.72%) and **jina-code-embeddings-1.5b** (78.94%) as dedicated code models. These are not in the DEM-122 scope but should be evaluated if Jina is shortlisted.
