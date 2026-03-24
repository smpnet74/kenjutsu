# E5-mistral-7b-instruct

**Provider:** Microsoft
**Category:** General-purpose embedding model (LLM-based, instruction-tuned)
**Date evaluated:** 2026-03-23
**Parent issue:** DEM-123

---

## 1. Model Overview

| Field | Value |
|---|---|
| Model name | E5-mistral-7b-instruct |
| Provider | Microsoft |
| Release date | Paper Dec 31, 2023; HuggingFace Jan 2024 |
| Architecture | Decoder-only LLM (Mistral-7B-v0.1 base), [EOS] token embedding, LoRA fine-tuned |
| Parameters | ~7B |
| Dimensions | 4096 |
| Max context window | 4,096 tokens |
| License | MIT |
| Category | General-purpose, LLM-based |
| HuggingFace | `intfloat/e5-mistral-7b-instruct` |

## 2. Benchmark Performance

### MTEB / BEIR Scores

| Category | Score |
|---|---|
| BEIR Retrieval (nDCG@10) | 56.9 |
| Overall MTEB | Was #1 at release; outperformed prior SOTA by 2.4 pts |
| Classification | Not confirmed from citable source |
| Clustering | Not confirmed from citable source |
| STS | Not confirmed from citable source |

### Code-Specific Benchmarks (CoIR — ACL 2025)

| Benchmark | Score (nDCG@10) |
|---|---|
| **CoIR average** | **55.18 — Rank 2/10** |
| SQL | 65.98 |
| Contest code | 82.55 |
| StackOverflow QA | 91.54 |
| APPS | 21.33 |
| CoSQA | 31.27 |

**This is the best-performing general-purpose model in the CoIR code retrieval benchmark.** It trails only Voyage-Code-002 (56.26) by ~1 point. The instruction-tuning capability allows task-specific optimization that other general-purpose models cannot match.

## 3. Technical Capabilities

| Capability | Status |
|---|---|
| Matryoshka (MRL) | Not supported |
| Quantization | INT8/INT4 via bitsandbytes |
| Instruction-tuned | **Yes** — full flexible natural-language task instructions on queries |
| Multi-lingual | English recommended only (limited multilingual from fine-tuning data) |
| Sparse + dense hybrid | Dense only |

The instruction-tuning is the key differentiator. Queries use the format:
```text
Instruct: {task description}\nQuery: {query}
```
Documents are encoded without prefix. Different instructions per task type enable the model to adapt its embedding space to the specific retrieval task.

## 4. Deployment & Infrastructure

### Self-Hosted

| Precision | VRAM |
|---|---|
| FP16 | ~14 GB (weights); 20–24 GB recommended for batched production |
| INT8 | ~7–8 GB |

Recommended GPU: A100 40GB, RTX 4090 (24GB), or A10G (24GB).

### Managed API

| Provider | Price per 1M tokens |
|---|---|
| SambaNova Cloud | Free tier available |
| Gcore Inference | Available |
| Replicate | ~$0.059 (estimated) |

### Framework Support

sentence-transformers, HuggingFace Transformers, TEI, Safetensors, MLX (community).

## 5. Code Retrieval Suitability

**Strengths:**
- **#2 in CoIR code retrieval benchmark** — best general-purpose model evaluated
- Only 1 point behind Voyage-Code-002 (the best code-specialized model in CoIR)
- Flexible instruction-tuning enables code-specific query optimization
- Strong scores on SQL (65.98), contest code (82.55), and StackOverflow QA (91.54)
- MIT license — no commercial restrictions
- 4,096-token context window handles most code functions/classes

**Weaknesses:**
- 7B parameters requires significant GPU resources (~14+ GB VRAM)
- 4096-dimensional output inflates storage and search costs
- No MRL support — cannot reduce dimensions
- Weak on some code tasks: APPS (21.33), CoSQA (31.27)
- Limited multilingual capability
- Slower than encoder-based models for high-throughput indexing

**Comparison to code-specialized models:**
E5-mistral-7b-instruct (55.18) is within 1.08 points of Voyage-Code-002 (56.26) on CoIR average. This is the strongest evidence that a general-purpose model can match code-specialized models on code retrieval. The gap is within noise for many practical applications.

**Multi-language code support:** Strong on SQL, contest code (Python-heavy), and StackOverflow QA. Weaker on APPS (algorithmic code) and CoSQA (Python search). Performance likely varies by programming language but no per-language breakdown is available.

## 6. Overall Assessment

| Field | Value |
|---|---|
| Recommendation | **Strong candidate** |
| Best use case | Primary embedding model for code retrieval in Kenjutsu; instruction-tuned queries for code search |
| Key trade-offs | Near code-specialized performance with general-purpose flexibility, but high resource requirements and no dimension reduction |

E5-mistral-7b-instruct is the standout finding in this evaluation. It demonstrates that an instruction-tuned LLM-based embedding model can nearly match code-specialized models on code retrieval (CoIR rank 2/10, within 1 point of #1). The instruction-tuning capability enables Kenjutsu to optimize query embeddings for different code search tasks without retraining. The main concern is resource intensity — at 7B parameters and 4096 dimensions, it requires substantial GPU and storage infrastructure. If infrastructure budget allows, this is a strong primary candidate. Consider pairing with a lighter model for bulk indexing and using E5-mistral for query-time embeddings.
