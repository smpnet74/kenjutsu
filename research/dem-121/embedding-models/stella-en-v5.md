# Stella-EN-v5

**Provider:** dunzhang / NovaSearch
**Category:** General-purpose embedding model (strong MTEB contender)
**Date evaluated:** 2026-03-23
**Parent issue:** DEM-123

---

## 1. Model Overview

Two variants exist as a family. The 1.5B variant is the flagship.

| Property | stella_en_400M_v5 | stella_en_1.5B_v5 |
|---|---|---|
| Provider | dunzhang / NovaSearch | dunzhang / NovaSearch |
| Release date | July 2024 | July 2024 |
| Base model | Alibaba-NLP/gte-large-en-v1.5 | Alibaba-NLP/gte-Qwen2-1.5B-instruct |
| Architecture | Transformer++ encoder | Decoder-only (Qwen2) with bidirectional attention |
| Parameters | ~400M | ~1.5B |
| Dimensions | 512/768/1024/2048/4096/6144/8192 (MRL) | Same 7 dimension options |
| Max context window | 512 tokens (trained at 512) | 512 tokens effective (inherits Qwen2 131K but unvalidated) |
| License | MIT | MIT |
| Paper | arXiv:2412.19048 | arXiv:2412.19048 |
| HuggingFace | `dunzhang/stella_en_400M_v5` | `dunzhang/stella_en_1.5B_v5` |

## 2. Benchmark Performance

### MTEB Scores — stella_en_1.5B_v5

| Category | Score |
|---|---|
| Overall | **71.19** |
| Retrieval | 61.01 |
| Classification | 87.63 |
| Clustering | 57.69 |
| STS | 84.51 |

### MTEB Scores — stella_en_400M_v5

Aggregate scores not published. Individual task scores appear on HuggingFace card (e.g., STSBenchmark: 87.74, ArguAna: 64.24) but no category rollups available.

**Note:** Accurate evaluation requires `max_len=400`, `bfloat16`, and no normalization for classification tasks. Score discrepancies have been reported in community reproductions without these settings.

### Code-Specific Benchmarks

None. No code data in training. Not evaluated on CodeSearchNet, CoSQA, or CoIR.

## 3. Technical Capabilities

| Capability | Status |
|---|---|
| Matryoshka (MRL) | **Yes** — 7 dimension choices (512 to 8192); 1024d is within 0.001 of 8192d |
| Quantization | Standard via framework; bfloat16 inference required |
| Instruction-tuned | Yes — two instruction prompts (s2p for retrieval, s2s for STS) |
| Multi-lingual | English only |
| Sparse + dense hybrid | Dense only |

The MRL implementation is notable — 1024 dimensions captures virtually all quality of the full 8192 dimensions, enabling significant storage savings.

## 4. Deployment & Infrastructure

### Self-Hosted

| Variant | VRAM |
|---|---|
| 400M | ~2–3 GB inference |
| 1.5B | ~6.2 GB inference (third-party estimate) |

bfloat16 is required for accurate scores.

### Managed API

No managed API. No inference provider deployment. Self-hosting only.

### Framework Support

sentence-transformers, HuggingFace Transformers, ONNX, Safetensors, TEI, Infinity (Docker), Candle (Rust — 1.5B variant).

## 5. Code Retrieval Suitability

**Strengths:**
- Second-highest overall MTEB score (71.19) after NV-Embed-v2 — and with MIT license
- Excellent MRL support — 7 dimension choices with negligible quality loss at 1024d
- Strong retrieval scores (61.01) approaching NV-Embed-v2 levels
- MIT license — no commercial restrictions
- 1.5B variant is relatively lightweight (~6 GB VRAM)
- Instruction-tuned for task-specific optimization

**Weaknesses:**
- 512-token context window is severely limiting for code files
- No code-specific training or benchmarks
- No managed API — self-hosting only
- bfloat16 requirement adds deployment complexity
- 131K context from Qwen2 base is unvalidated — treat effective limit as 512
- English only

**Comparison to code-specialized models:**
No code retrieval data exists. Strong general retrieval (61.01) suggests potential, but the 512-token context window makes it impractical for code regardless.

**Multi-language code support:** Not applicable — English only, no code training.

## 6. Overall Assessment

| Field | Value |
|---|---|
| Recommendation | **Not recommended** (despite strong general scores) |
| Best use case | High-quality short text embedding with dimension flexibility |
| Key trade-offs | Excellent MTEB scores and MRL, but 512-token context window is fatal for code retrieval |

Stella-EN-v5 achieves impressive general MTEB scores (71.19 for 1.5B, nearly matching NV-Embed-v2's 72.31 at 1/5 the parameters) with a MIT license. However, the 512-token effective context window makes it unsuitable for code retrieval — most code functions and classes exceed this limit. If the context window were extended and validated at longer lengths, this would be a strong contender. As-is, it's limited to short-text applications.
