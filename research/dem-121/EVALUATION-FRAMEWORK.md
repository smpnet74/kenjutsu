# Embedding Model Evaluation Framework

- **Status:** active
- **Author:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-121
- **Parent:** DEM-121

---

## Purpose

This framework standardizes the evaluation of embedding models for Kenjutsu's code review pipeline. Every model evaluation follows the same template and criteria to enable direct comparison.

## Evaluation Dimensions

### 1. Model Identity

- Full model name and version
- Organization / provider
- Release date
- Architecture (encoder-only, decoder-based, etc.)
- Parameter count
- License

### 2. Technical Specifications

| Property | Value |
|---|---|
| Context window | tokens |
| Embedding dimensions | default / flexible |
| Matryoshka support | Yes/No (which dimensions) |
| Binary quantization | Native / Post-hoc / None |
| int8 quantization | Yes/No |

### 3. Benchmark Performance

**General benchmarks:**
- MTEB overall score
- MTEB retrieval score (nDCG@10)

**Code-specific benchmarks:**
- CodeSearchNet MRR@10 (per-language breakdown)
- CoIR average score
- Other code retrieval benchmarks (AdvTest, CosQA+, etc.)

**Benchmark reliability notes:**
- Flag CoSQA scores as unreliable (~51% mislabeled)
- Note self-reported vs. independently verified scores
- Distinguish zero-shot vs. fine-tuned performance

### 4. Code Retrieval Capabilities

- NL → code retrieval quality
- Code → code retrieval quality
- Cross-language code retrieval
- Programming languages supported (count and list)

### 5. Deployment & Cost

| Property | Value |
|---|---|
| API pricing | $/1M tokens |
| Self-hosted | Yes/No (open weights?) |
| GPU requirements | (for self-hosted) |
| Latency (P50/P99) | ms |
| Throughput | tokens/hour |

### 6. Kenjutsu Fit Assessment

Rate each on a 1-5 scale:

- **Code retrieval quality** — How well does it retrieve relevant code?
- **Context window adequacy** — Can it handle function-level and file-level chunks?
- **Deployment flexibility** — API + self-hosted options?
- **Cost efficiency** — Price per 1M tokens at scale?
- **Dimension flexibility** — Matryoshka/quantization for storage optimization?
- **Ecosystem maturity** — Community, documentation, integrations?

### 7. Verdict

- **Recommendation:** Strong candidate / Viable alternative / Not recommended / Baseline only
- **Best use case within Kenjutsu:** (specific pipeline stage)
- **Key risk:** (primary concern)

---

## Benchmark Reliability Guide

| Benchmark | Reliability | Notes |
|---|---|---|
| MTEB (English) | High | Broad coverage, community-maintained |
| CoIR | High | Code-specific, multi-task, recent |
| CodeSearchNet | Medium | Well-established but dated; MRR variance across languages |
| CoSQA | **Low** | ~51% mislabeled pairs (Bing queries vs CodeSearchNet code) |
| CosQA+ | Medium-High | 412K pairs, 1K human-verified; replacement for CoSQA |
| AdvTest | Medium | Tests adversarial robustness of code retrieval |
| Self-reported vendor benchmarks | Low-Medium | Often cherry-picked; verify methodology |

---

## Embedding Model Evaluation Template

```markdown
# {Model Name} — Embedding Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** YYYY-MM-DD
- **Issue:** DEM-122

---

## 1. Model Identity

| Property | Value |
|---|---|
| Full name | |
| Organization | |
| Release date | |
| Architecture | |
| Parameters | |
| License | |

## 2. Technical Specifications

| Property | Value |
|---|---|
| Context window | |
| Default dimensions | |
| Flexible dimensions | |
| Matryoshka support | |
| Binary quantization | |
| int8 quantization | |

## 3. Benchmark Performance

### General

| Benchmark | Score |
|---|---|
| MTEB overall | |
| MTEB retrieval | |

### Code-Specific

| Benchmark | Score |
|---|---|
| CodeSearchNet MRR@10 (avg) | |
| CoIR average | |

### CodeSearchNet Per-Language (MRR@10 or nDCG@10)

| Language | Score |
|---|---|
| Python | |
| JavaScript | |
| Go | |
| Java | |
| PHP | |
| Ruby | |

## 4. Code Retrieval Capabilities

- **NL → code:**
- **Code → code:**
- **Cross-language:**
- **Languages supported:**

## 5. Deployment & Cost

| Property | Value |
|---|---|
| API pricing | |
| Self-hosted | |
| GPU requirements | |
| Latency | |

## 6. Kenjutsu Fit (1-5)

| Criterion | Score | Notes |
|---|---|---|
| Code retrieval quality | | |
| Context window adequacy | | |
| Deployment flexibility | | |
| Cost efficiency | | |
| Dimension flexibility | | |
| Ecosystem maturity | | |

## 7. Verdict

- **Recommendation:**
- **Best use case:**
- **Key risk:**
```
