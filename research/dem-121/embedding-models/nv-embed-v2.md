# NV-Embed-v2

**Provider:** NVIDIA
**Category:** General-purpose embedding model (LLM-based, MTEB #1 at release)
**Date evaluated:** 2026-03-23
**Parent issue:** DEM-123

---

## 1. Model Overview

| Field | Value |
|---|---|
| Model name | NV-Embed-v2 |
| Provider | NVIDIA |
| Release date | August 30, 2024 |
| Architecture | Decoder-only LLM (Mistral-7B-v0.1 base), Latent-Attention pooling |
| Parameters | ~7.85B |
| Dimensions | 4096 (fixed) |
| Max context window | 32,768 tokens |
| License | **CC-BY-NC-4.0 (non-commercial only)** |
| Category | General-purpose, LLM-based |
| HuggingFace | `nvidia/NV-Embed-v2` |
| Paper | arXiv:2405.17428 |

The Latent-Attention pooling mechanism is novel — the LLM attends to learned latent vectors to produce embeddings, rather than using last-token or mean pooling.

## 2. Benchmark Performance

### MTEB Scores (56 datasets) — Was #1 at Release

| Category | Score |
|---|---|
| **Overall** | **72.31** |
| Retrieval (15 tasks) | 62.65 |
| Classification (12 tasks) | 90.37 |
| Clustering (11 tasks) | 58.46 |
| STS (10 tasks) | 84.31 |
| Reranking (4 tasks) | 60.65 |
| Pair Classification (3 tasks) | 88.67 |
| Summarization (1 task) | 30.70 |

### Code-Specific Benchmarks

| Benchmark | Score | Notes |
|---|---|---|
| CodeSearchNet | Not evaluated | CodeSearchNet data is in training set |
| CoSQA | Not evaluated | |
| CoIR | Not evaluated | |

No code retrieval evaluation results are published despite CodeSearchNet being part of the ~7M labeled training samples. Code retrieval capability is unverified.

## 3. Technical Capabilities

| Capability | Status |
|---|---|
| Matryoshka (MRL) | **Not supported** — fixed 4096 dimensions |
| Quantization | No official support (FP16 only; community bitsandbytes/GGUF attempts exist) |
| Instruction-tuned | **Yes** — two-staged instruction tuning; task-specific query prefixes required |
| Multi-lingual | English only (confirmed in HF discussions) |
| Sparse + dense hybrid | Dense only |

Query format requires explicit task instructions:
```text
Instruct: Given a question, retrieve passages that answer the question
Query: {query}
```
Documents have no prefix. Different instructions per task type.

## 4. Deployment & Infrastructure

### Self-Hosted

| Precision | VRAM | Notes |
|---|---|---|
| FP16 | ~15.7 GB (theoretical); **24–30 GB observed** | Higher due to Latent-Attention overhead |
| INT8 | ~8 GB (theoretical) | Not officially tested |
| INT4 | ~4 GB (theoretical) | Not officially tested |

- **Minimum recommended:** 48 GB VRAM (NVIDIA L40S or A100)
- **Requires Flash Attention 2** (Ampere+ GPUs: A100, A10G, RTX 3090/4090, H100)
- Confirmed working: NVIDIA L40S (48 GB) on AWS EC2 g6e.xlarge
- At capacity: RTX 4090 (24 GB) in FP32 mode
- Required dependencies: `torch==2.2.0`, `transformers==4.42.4`, `flash-attn==2.2.0`

### Managed API

| Provider | Notes |
|---|---|
| build.nvidia.com | Free for NVIDIA Developer Program (prototyping); v2 status unclear |
| NVIDIA NIM | **NV-Embed-v2 is NOT listed in NIM support matrix** |
| NVIDIA AI Enterprise | ~$4,500/GPU/year or ~$1/GPU/hour (not per-token) |

**Critical gap:** The HuggingFace model is CC-BY-NC-4.0 (non-commercial). The NIM pathway that would enable commercial use does not list NV-Embed-v2. Commercial deployment may not be legally possible.

### Framework Support

HuggingFace Transformers (`trust_remote_code=True` required), sentence-transformers (v2.7.0+), DataParallel multi-GPU. Flash Attention 2 is a hard dependency. No ONNX support.

## 5. Code Retrieval Suitability

**Strengths:**
- Highest overall MTEB score in this evaluation (72.31)
- Highest retrieval score (62.65 BEIR) among general-purpose models evaluated
- 32K context window handles entire files
- Instruction-tuning enables task-specific optimization
- Strong across all MTEB categories

**Weaknesses:**
- **CC-BY-NC-4.0 license prohibits commercial use**
- **Not available in NVIDIA NIM for commercial deployment**
- Requires 48 GB VRAM minimum — most expensive to self-host
- 4096-dim fixed output with no MRL — highest storage cost
- No code retrieval benchmarks published
- Flash Attention 2 hard dependency limits hardware options
- English only
- Pinned dependency versions create maintenance burden

**Comparison to code-specialized models:**
Cannot be compared — no code benchmarks exist. The high general retrieval score (62.65) suggests potential, but the CoIR paper demonstrated that general retrieval performance does not predict code retrieval performance.

**Multi-language code support:** English only. Not suitable for multilingual codebases.

## 6. Overall Assessment

| Field | Value |
|---|---|
| Recommendation | **Not recommended** |
| Best use case | Research/academic use only due to license restrictions |
| Key trade-offs | Highest MTEB scores but disqualified by non-commercial license, extreme resource requirements, and no code benchmarks |

NV-Embed-v2 achieves the highest MTEB scores in this evaluation, but it is effectively disqualified for Kenjutsu by three factors: (1) CC-BY-NC-4.0 license prohibits commercial use, (2) it requires 48+ GB VRAM making it the most expensive model to self-host, and (3) no code retrieval benchmarks exist to validate the primary use case. The non-commercial license is the fatal flaw — unless NVIDIA releases a commercially-licensed version via NIM, this model cannot be used in production.
