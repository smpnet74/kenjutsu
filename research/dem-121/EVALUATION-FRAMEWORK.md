# Embedding Model Evaluation Framework

**Parent issue:** DEM-121
**Created:** 2026-03-23
**Purpose:** Standardized evaluation criteria for embedding models under consideration for Kenjutsu's code retrieval pipeline.

---

## Evaluation Template

Each model evaluation file follows this structure:

### 1. Model Overview
- **Model name**
- **Provider / Organization**
- **Release date**
- **Architecture** (encoder type, base model)
- **Parameters** (total count)
- **Dimensions** (output embedding size, variable dimension support)
- **Max context window** (tokens)
- **License**
- **Category** (code-specialized / general-purpose with code capability)

### 2. Benchmark Performance

#### MTEB Scores
- **Overall MTEB score** (if available)
- **Retrieval subset score**
- **Classification subset score**
- **Clustering subset score**
- **STS (Semantic Textual Similarity) subset score**

#### Code-Specific Benchmarks
- **CodeSearchNet** (if evaluated)
- **CoSQA** (Code Search QA, if evaluated)
- **Other code retrieval benchmarks**
- **Custom evaluations / reported code performance**

### 3. Technical Capabilities
- **Matryoshka Representation Learning (MRL)** — supports variable-dimension truncation?
- **Quantization support** — binary, int8, or other quantized variants?
- **Instruction-tuned** — supports task-specific prefixes/instructions?
- **Multi-lingual support** — languages covered
- **Sparse + dense hybrid** — supports both retrieval modes?

### 4. Deployment & Infrastructure
- **Self-hosted feasibility**
  - VRAM requirements (FP16, INT8, INT4)
  - Recommended GPU
  - Inference speed (queries/sec on reference hardware)
- **Managed API availability**
  - Provider(s) and pricing
  - Rate limits
- **Framework support** (sentence-transformers, HuggingFace, ONNX, TensorRT, etc.)

### 5. Code Retrieval Suitability
- **Strengths for code retrieval** — what makes this model relevant
- **Weaknesses for code retrieval** — known gaps or concerns
- **Comparison to code-specialized models** — how it stacks up against Voyage-code-3, CodeSage, etc.
- **Multi-language code support** — Python, JS/TS, Go, Rust, Java, etc.

### 6. Overall Assessment
- **Recommendation** (Strong candidate / Worth considering / Not recommended)
- **Best use case within Kenjutsu** — where this model fits (if anywhere)
- **Key trade-offs** — what you gain vs. what you give up

---

## Scoring Rubric

When comparing models, use the following criteria weights for Kenjutsu's use case:

| Criterion | Weight | Rationale |
|---|---|---|
| Code retrieval accuracy | 30% | Primary use case — retrieving relevant code context for review |
| General text retrieval | 15% | PR descriptions, commit messages, documentation |
| Context window size | 15% | Larger files and multi-file context require longer windows |
| Self-hosting feasibility | 15% | Must be deployable on reasonable infrastructure |
| Dimension flexibility (MRL) | 10% | Enables cost/quality trade-offs at query time |
| Latency / throughput | 10% | Real-time PR review requires fast embedding |
| Ecosystem / maturity | 5% | Community support, documentation, production track record |

---

## File Naming Convention

Files are stored in `research/dem-121/embedding-models/` using the pattern:
- `{model-name}.md` (lowercase, hyphenated)

Examples:
- `voyage-code-3.md`
- `bge-large-en-v1.5.md`
- `gte-qwen2.md`
