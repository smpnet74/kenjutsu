# E5-large-v2

**Provider:** Microsoft
**Category:** General-purpose embedding model
**Date evaluated:** 2026-03-23
**Parent issue:** DEM-123

---

## 1. Model Overview

| Field | Value |
|---|---|
| Model name | E5-large-v2 |
| Provider | Microsoft |
| Release date | Paper Dec 2022; HuggingFace May 2023 |
| Architecture | BERT-large encoder (initialized from `bert-large-uncased-whole-word-masking`), 24 layers, mean pooling |
| Parameters | 335M |
| Dimensions | 1024 |
| Max context window | 512 tokens |
| License | MIT |
| Category | General-purpose |
| HuggingFace | `intfloat/e5-large-v2` |

## 2. Benchmark Performance

### MTEB / BEIR Scores

| Category | Score |
|---|---|
| BEIR Retrieval (nDCG@10) | 50.6 |
| Overall MTEB | Not confirmed from citable source (leaderboard JS-rendered) |
| Classification | Not confirmed |
| Clustering | Not confirmed |
| STS | Not confirmed |

### Code-Specific Benchmarks

| Benchmark | Score | Notes |
|---|---|---|
| CoIR average (E5-base-v2 proxy) | 50.90 nDCG@10 | **Rank 3/10** — only E5-base was evaluated, not E5-large |
| CodeSearchNet | Not directly evaluated for E5-large-v2 |
| CoSQA | Not directly evaluated for E5-large-v2 |

Notable: E5-base-v2 (110M params) ranked 3rd in CoIR with 50.90 avg, significantly outperforming many larger general-purpose models. The E5 training methodology appears to transfer well to code retrieval.

## 3. Technical Capabilities

| Capability | Status |
|---|---|
| Matryoshka (MRL) | Not supported |
| Quantization | Standard FP16/INT8 via framework |
| Instruction-tuned | Partial — fixed `query:` / `passage:` prefixes only (not flexible instructions) |
| Multi-lingual | English only |
| Sparse + dense hybrid | Dense only |

## 4. Deployment & Infrastructure

### Self-Hosted

| Precision | VRAM |
|---|---|
| FP16 | ~0.67 GB |
| INT8 | ~0.35 GB |

Extremely lightweight. Runs on any hardware.

### Managed API

| Provider | Price per 1M tokens |
|---|---|
| OpenRouter / DeepInfra | $0.01 |
| SambaNova | Free tier available |
| Pinecone Inference | Available |

### Framework Support

sentence-transformers, HuggingFace Transformers, ONNX, OpenVINO, TEI, Safetensors.

## 5. Code Retrieval Suitability

**Strengths:**
- E5 family shows surprisingly strong code retrieval (base variant rank 3/10 in CoIR)
- Extremely lightweight and cheap to self-host
- MIT license
- Well-established with extensive community support
- Strong general retrieval baseline (BEIR 50.6)

**Weaknesses:**
- 512-token context window is too short for code files
- No MRL or instruction-tuning flexibility
- English only
- E5-large-v2 itself was not evaluated in CoIR (only E5-base)
- Aging architecture — multiple generations behind

**Comparison to code-specialized models:**
E5-base-v2's CoIR score (50.90) is surprisingly close to code-specialized models (Voyage-Code-002: 56.26). The gap is only ~5 points, suggesting the E5 training methodology captures useful code semantics. E5-large-v2 would likely score higher than E5-base-v2, but this is unconfirmed.

**Multi-language code support:** Not specifically trained on code, but the E5 family's performance suggests latent code understanding from web training data.

## 6. Overall Assessment

| Field | Value |
|---|---|
| Recommendation | **Not recommended** (but E5 family methodology is notable) |
| Best use case | Lightweight baseline; E5-mistral-7b-instruct is the preferred E5 variant for code retrieval |
| Key trade-offs | Surprisingly good code retrieval proxy scores for its size, but 512-token limit and lack of modern features are disqualifying |

E5-large-v2 is outclassed by its successor E5-mistral-7b-instruct in every dimension. The 512-token context window alone makes it unsuitable for code retrieval. However, the E5 family's unexpectedly strong code retrieval performance (E5-base rank 3/10 in CoIR) validates the methodology and points toward E5-mistral-7b-instruct as the model to watch.
