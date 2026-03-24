# UniXcoder — Embedding Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-122

---

## 1. Model Identity

| Property | Value |
|---|---|
| Full name | UniXcoder (unixcoder-base) |
| Organization | Microsoft Research |
| Release date | March 2022 (ACL 2022) |
| Architecture | RoBERTa-base with unified cross-modal pre-training; supports encoder-only, decoder-only, and encoder-decoder modes via prefix attention masks |
| Parameters | ~125M |
| License | MIT |

## 2. Technical Specifications

| Property | Value |
|---|---|
| Context window | 1,024 tokens |
| Default dimensions | 768 |
| Flexible dimensions | No |
| Matryoshka support | No |
| Binary quantization | No |
| int8 quantization | No |

### Unique Architecture Feature

UniXcoder incorporates **three modalities** into a single model:
1. Natural language (comments, docstrings)
2. Code tokens (source code)
3. AST (Abstract Syntax Tree) sequences

This cross-modal pre-training enables the model to understand structural code relationships that token-only models miss.

## 3. Benchmark Performance

### General

| Benchmark | Score |
|---|---|
| MTEB overall | Not submitted |
| CoIR average | 37.33 (significantly behind modern models) |

### Code-Specific: CodeSearchNet MRR@10

| Language | UniXcoder | GraphCodeBERT | CodeBERT |
|---|---|---|---|
| Ruby | 74.0% | 70.3% | 67.9% |
| JavaScript | 68.4% | 64.4% | 62.0% |
| Go | 91.5% | 89.7% | 88.2% |
| Python | 72.0% | 69.2% | 67.2% |
| Java | 72.6% | 69.1% | 67.6% |
| PHP | 67.6% | 64.9% | 62.8% |
| **Average** | **74.4%** | **71.3%** | **69.3%** |

UniXcoder was state-of-the-art for code search at its release. It has since been significantly surpassed — CoCoSoDa (2022) beat it by 5.9% average MRR shortly after. Modern models (Voyage-code-3, Nomic Embed Code) exceed it by 10+ points.

## 4. Code Retrieval Capabilities

- **NL → code:** Good for its era (74.4% CSN MRR). Now significantly behind modern models.
- **Code → code:** Supported through encoder-only mode.
- **Cross-language:** Not explicitly designed for cross-language retrieval.
- **Languages supported:** 6 base (Java, Ruby, Python, PHP, JavaScript, Go); 9 with `unixcoder-base-nine` variant (adds C, C++, C#)

## 5. Deployment & Cost

| Property | Value |
|---|---|
| API pricing | No hosted API |
| Self-hosted | Yes — MIT license; weights on HuggingFace (`microsoft/unixcoder-base`) |
| GPU requirements | Minimal (~125M params); runs on CPU |
| Latency | Very fast; small model |

## 6. Kenjutsu Fit (1-5)

| Criterion | Score | Notes |
|---|---|---|
| Code retrieval quality | 2 | Was SOTA in 2022; now 10+ points behind modern models |
| Context window adequacy | 1 | 1,024 tokens too small |
| Deployment flexibility | 5 | Open-source (MIT); tiny; runs anywhere |
| Cost efficiency | 5 | Free; runs on CPU |
| Dimension flexibility | 1 | Fixed 768-dim |
| Ecosystem maturity | 3 | Well-cited in research; still used as fine-tuning backbone |

## 7. Verdict

- **Recommendation:** **Baseline only** — historically significant but not competitive for production
- **Best use case:** Research baseline for measuring progress. Fine-tuning backbone if AST-awareness is desired. The cross-modal architecture (NL + code + AST) is architecturally interesting and may inform custom model training.
- **Key risk:** 1K context window, 768 fixed dimensions, and 74.4% MRR (vs 90%+ for modern models) make it unsuitable for production code retrieval. No active development.
- **Historical significance:** Pioneered unified NL-code-AST pre-training. Demonstrated that incorporating AST structure improves code understanding beyond token-only approaches. This insight carries forward to modern architectures.
