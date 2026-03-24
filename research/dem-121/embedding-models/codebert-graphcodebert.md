# CodeBERT / GraphCodeBERT — Embedding Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-122

---

This evaluation covers both models as they form a family: GraphCodeBERT extends CodeBERT with structural code understanding.

---

## Model A: CodeBERT

### 1. Model Identity

| Property | Value |
|---|---|
| Full name | CodeBERT |
| Organization | Microsoft Research |
| Release date | February 2020 (EMNLP 2020) |
| Architecture | RoBERTa-base; bimodal pre-training on (NL docstring, PL function) pairs |
| Parameters | 125M |
| License | MIT |

### 2. Technical Specifications

| Property | Value |
|---|---|
| Context window | 512 tokens |
| Default dimensions | 768 |
| Flexible dimensions | No |
| Matryoshka support | No |
| Binary quantization | No |
| int8 quantization | No |

### 3. Training

Pre-trained with two objectives:
1. **Masked Language Modeling (MLM)** on NL-PL bimodal data
2. **Replaced Token Detection (RTD)** — distinguishing real vs. replaced tokens

Training data: CodeSearchNet corpus (2.1M bimodal data points + 6.4M unimodal code)

### 4. Benchmark Performance

| Benchmark | Score |
|---|---|
| CodeSearchNet MRR@10 (avg) | 69.3% |
| Clone detection F1 | 94.1% |
| CoIR average | Not submitted |

---

## Model B: GraphCodeBERT

### 1. Model Identity

| Property | Value |
|---|---|
| Full name | GraphCodeBERT |
| Organization | Microsoft Research |
| Release date | September 2020 (ICLR 2021) |
| Architecture | Extends CodeBERT (RoBERTa-base) with **data flow graph** integration; graph-guided masked attention |
| Parameters | 125M |
| License | MIT |

### 2. Technical Specifications

| Property | Value |
|---|---|
| Context window | 512 code tokens + 128 DFG nodes + 128 NL tokens |
| Default dimensions | 768 |
| Flexible dimensions | No |
| Matryoshka support | No |
| Binary quantization | No |
| int8 quantization | No |

### 3. Data Flow Graph Innovation

GraphCodeBERT's key contribution is incorporating **data flow graphs** (DFGs) into the pre-training process:

- **DFG vs AST:** Data flow tracks "where the value comes from" (semantic, variable-definition relationships) vs AST which encodes syntactic structure. DFGs are more compact and computationally tractable.
- **Extraction:** DFGs are extracted via tree-sitter parsers
- **Attention:** Graph-guided masked attention propagates data flow dependencies through the transformer layers
- **Result:** +2.0 MRR points over CodeBERT on code search; improved clone detection and code translation

### 4. Benchmark Performance

| Benchmark | Score |
|---|---|
| CodeSearchNet MRR@10 (avg) | 71.3% |
| Clone detection F1 | 95.0% |
| CoIR average | Not submitted |

---

## CodeSearchNet Per-Language Comparison (MRR@10)

| Language | CodeBERT | GraphCodeBERT | Delta |
|---|---|---|---|
| Ruby | 67.9% | 70.3% | +2.4 |
| JavaScript | 62.0% | 64.4% | +2.4 |
| Go | 88.2% | 89.7% | +1.5 |
| Python | 67.2% | 69.2% | +2.0 |
| Java | 67.6% | 69.1% | +1.5 |
| PHP | 62.8% | 64.9% | +2.1 |
| **Average** | **69.3%** | **71.3%** | **+2.0** |

## Languages Supported

Both models: 6 languages (Java, Python, PHP, Go, JavaScript, Ruby)

## Deployment & Cost

| Property | CodeBERT | GraphCodeBERT |
|---|---|---|
| API pricing | No hosted API | No hosted API |
| Self-hosted | Yes (MIT, HuggingFace) | Yes (MIT, HuggingFace) |
| GPU requirements | Minimal (125M); CPU-capable | Minimal (125M); CPU-capable |
| Latency | Very fast | Very fast |
| HuggingFace | `microsoft/codebert-base` | `microsoft/graphcodebert-base` |

## Kenjutsu Fit (1-5)

| Criterion | CodeBERT | GraphCodeBERT | Notes |
|---|---|---|---|
| Code retrieval quality | 2 | 2 | 69–71% MRR vs 90%+ for modern models |
| Context window adequacy | 1 | 1 | 512 tokens is severely limiting |
| Deployment flexibility | 5 | 5 | Open (MIT), tiny, runs on CPU |
| Cost efficiency | 5 | 5 | Free; minimal compute |
| Dimension flexibility | 1 | 1 | Fixed 768-dim |
| Ecosystem maturity | 4 | 4 | Foundational; widely cited and used in research |

## Verdict

### CodeBERT
- **Recommendation:** **Baseline only** — the foundational model that established NL+PL pre-training
- **Historical significance:** First large-scale bimodal NL+PL pre-trained model. Established the paradigm that all subsequent code embedding models build upon.

### GraphCodeBERT
- **Recommendation:** **Baseline only** — demonstrates the value of structural code understanding
- **Historical significance:** Proved that data flow graph integration improves code understanding (+2 MRR points). This insight informs Kenjutsu's architecture: incorporating structural code signals (AST, DFG) alongside embeddings improves retrieval quality.

### Both Models
- **Best use case:** Research baselines for measuring improvement. The architectural insights (bimodal pre-training, DFG integration) are more valuable than the models themselves.
- **Key risk:** 512-token context window, fixed 768 dimensions, and 69–71% MRR make them unsuitable for production code retrieval. No active development; superseded by UniXcoder, CodeSage, Voyage-code-3, and others.
- **Architectural insight for Kenjutsu:** GraphCodeBERT's data flow approach validates that structural code understanding (not just token-level) improves retrieval. Kenjutsu should consider incorporating DFG or AST signals regardless of which embedding model is chosen.
