# Linq-Embed-Mistral

**Provider:** Linq AI Research
**Category:** General-purpose embedding model (LLM-based, Mistral fine-tune)
**Date evaluated:** 2026-03-23
**Parent issue:** DEM-123

---

## 1. Model Overview

| Field | Value |
|---|---|
| Model name | Linq-Embed-Mistral |
| Provider | Linq AI Research |
| Release date | May 29, 2024 (MTEB snapshot); Paper December 2024 |
| Architecture | Decoder-only (Mistral-7B-v0.1 base), fine-tuned via LoRA from E5-mistral-7b-instruct, last-token pooling |
| Parameters | ~7B |
| Dimensions | 4096 |
| Max context window | 4,096 tokens (evaluation uses doc truncation at 256, queries at 128) |
| License | **CC-BY-NC-4.0 (non-commercial only)** |
| Category | General-purpose, LLM-based |
| HuggingFace | `Linq-AI-Research/Linq-Embed-Mistral` |
| Paper | arXiv:2412.03223 |

## 2. Benchmark Performance

### MTEB Scores (56 datasets)

| Category | Score |
|---|---|
| Overall average | 68.17 |
| Retrieval (15 tasks) | 60.19 — **#1 on MTEB leaderboard at release** |
| Classification | Not published in model card |
| Clustering | Not published |
| STS | Not published |

Was #1 among publicly accessible models and #3 overall on MTEB at release.

### Code-Specific Benchmarks

None. Not evaluated on CodeSearchNet, CoSQA, or CoIR. The MTEB English suite does not include a code retrieval subset.

## 3. Technical Capabilities

| Capability | Status |
|---|---|
| Matryoshka (MRL) | Not supported |
| Quantization | Community INT4/NF4 available (`ashercn97/Linq-Embed-Mistral-bnb-4bit`); ~40% speedup with minimal accuracy loss per technical report |
| Instruction-tuned | Yes — task-specific instruction prefix on queries (`Instruct: {task}\nQuery: {query}`) |
| Multi-lingual | Limited — primarily English; some Korean+English bilingual capability from base model |
| Sparse + dense hybrid | Dense only |

## 4. Deployment & Infrastructure

### Self-Hosted

| Precision | VRAM |
|---|---|
| FP16 | ~14–16 GB |
| INT8 | ~8–10 GB |
| INT4 (NF4) | ~4–6 GB (community quantized) |

Training hardware: 4x A100 80GB GPUs. No official VRAM benchmarks.

### Managed API

No managed API offered by Linq AI. Self-hosting via HuggingFace only.

### Framework Support

sentence-transformers, HuggingFace Transformers, Safetensors, bitsandbytes (INT4). No official ONNX support.

## 5. Code Retrieval Suitability

**Strengths:**
- Strong MTEB retrieval score (60.19, #1 at release)
- Instruction-tuned for task-specific query optimization
- Built on E5-mistral-7b-instruct (which scores #2 in CoIR code retrieval)
- 4K context window handles most code functions

**Weaknesses:**
- **CC-BY-NC-4.0 license prohibits commercial use** — same fatal flaw as NV-Embed-v2
- No code retrieval benchmarks published
- No managed API
- No MRL support
- Limited multilingual capability
- 7B parameters requires significant GPU resources
- 4096-dim fixed output inflates storage costs

**Comparison to code-specialized models:**
No code retrieval data. Built on E5-mistral-7b-instruct, which scores 55.18 on CoIR (rank 2/10). Whether the Linq fine-tuning preserves or improves code retrieval is unknown.

**Multi-language code support:** Not documented. English-primary.

## 6. Overall Assessment

| Field | Value |
|---|---|
| Recommendation | **Not recommended** |
| Best use case | Research/academic retrieval use only (non-commercial license) |
| Key trade-offs | Strong retrieval scores but disqualified by non-commercial license; its parent model E5-mistral-7b-instruct has MIT license and is a better choice |

Linq-Embed-Mistral is a LoRA fine-tune of E5-mistral-7b-instruct that improves MTEB scores but adds a CC-BY-NC-4.0 license restriction. For Kenjutsu's commercial use case, **E5-mistral-7b-instruct (MIT license) is strictly preferred** — it has the same architecture, proven code retrieval performance (CoIR rank 2), and no commercial restrictions. Linq-Embed-Mistral offers marginal MTEB improvement at the cost of commercial viability.
