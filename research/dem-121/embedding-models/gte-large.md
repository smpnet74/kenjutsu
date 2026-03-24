# GTE-Large (thenlper/gte-large)

**Researched:** 2026-03-23
**Source model card:** https://huggingface.co/thenlper/gte-large
**Paper:** Towards General Text Embeddings with Multi-stage Contrastive Learning (arXiv:2308.03281)

---

## 1. Model Overview

- **Model name:** GTE-Large (`thenlper/gte-large`)
- **Provider / Organization:** Alibaba DAMO Academy
- **Release date:** August 7, 2023
- **Architecture:** BERT-based encoder; standard BERT transformer backbone with average pooling over last hidden states
- **Parameters:** ~335M (model card reports 0.3B; the 434M figure cited elsewhere includes the v1.5 variant — see note below)
- **Dimensions:** 1024
- **Max context window:** 512 tokens (text beyond 512 is truncated)
- **License:** MIT
- **Category:** General-purpose with code capability

> **Note on versioning:** There are two distinct models under the "gte-large" name:
> - `thenlper/gte-large` — original DAMO release (Aug 2023), 512-token window, MIT license
> - `Alibaba-NLP/gte-large-en-v1.5` — updated release (2024), 8192-token window, 434M params, Apache 2.0, Transformer++ backbone (BERT + RoPE + GLU). The v1.5 is the more current model. Key differences are called out below where relevant.

---

## 2. Benchmark Performance

### MTEB Scores (thenlper/gte-large, original)

| Task Category | Score |
|---|---|
| Overall average (56 tasks) | 63.13 |
| Retrieval (15 tasks) | 52.22 |
| Classification (12 tasks) | 73.33 |
| Clustering (11 tasks) | 46.84 |
| STS / Semantic Textual Similarity (10 tasks) | 83.35 |
| Pair Classification (3 tasks) | 85.00 |
| Reranking (4 tasks) | 59.13 |
| Summarization (1 task) | 31.66 |

### MTEB Scores (Alibaba-NLP/gte-large-en-v1.5, updated)

| Task Category | Score |
|---|---|
| Overall average (56 tasks) | 65.39 |
| Retrieval (15 tasks) | 57.91 |
| Classification (12 tasks) | 77.75 |
| Clustering (11 tasks) | 47.95 |
| STS / Semantic Textual Similarity (10 tasks) | 81.43 |
| Pair Classification (3 tasks) | 84.63 |
| Reranking (4 tasks) | 58.50 |
| Summarization (1 task) | 30.91 |

LoCo long-context retrieval benchmark (v1.5 only): average 86.71 across 5 tasks.

### Code-Specific Benchmarks

GTE-Base (110M, the smaller sibling) was evaluated in the CoIR (Code Information Retrieval) benchmark paper (arXiv:2407.02883, ACL 2025). Results for GTE-Base on CoIR (nDCG@10):

| Task | GTE-Base Score |
|---|---|
| APPS | 3.24 |
| CoSQA | 30.24 |
| Synthetic Text2SQL | 46.19 |
| CodeSearchNet | 43.35 |
| CodeSearchNet-CCR | 35.50 |
| CodeTransOcean-DL | 33.81 |
| CodeTransOcean-Contest | 28.80 |
| StackOverflow QA | 62.71 |
| CodeFeedback-ST | 55.19 |
| CodeFeedback-MT | 28.48 |
| **Average** | **36.75** |

GTE-Base ranked 6th out of 9 models evaluated in CoIR, placing behind Voyage-Code-002 (56.26 avg), E5-Mistral (55.18), and BGE-M3. The paper explicitly notes: "GTE-Base ranks 6th in CoIR but 2nd in BEIR, indicating that models excelling in text retrieval may not necessarily perform well in code retrieval."

**GTE-Large specific CoIR scores:** Not available — the paper evaluated GTE-Base only. GTE-Large scores on CodeSearchNet or CoSQA are not published in any source located. Performance would be expected to be modestly better than GTE-Base given the larger parameter count, but no verified figures exist.

---

## 3. Technical Capabilities

- **Matryoshka Representation Learning (MRL):** Not supported. Fixed 1024-dimensional output only. (The v1.5 model, through the mGTE paper arXiv:2407.19669, gains Matryoshka-style elastic embeddings in the multilingual variant, but `gte-large-en-v1.5` does not advertise MRL on its model card.)
- **Quantization support:** The original model has 7 community-provided quantized variants on HuggingFace (GGUF format via `ChristianAzinn/gte-large-gguf`). Native model is F16/I64. No official quantized release from Alibaba.
- **Instruction-tuned:** No. The model does not use query/document instruction prefixes. Symmetric encoding — same approach for queries and documents.
- **Multi-lingual support:** English only. No multilingual capability in either the original or v1.5 English variant.
- **Sparse + dense hybrid retrieval:** Not supported. Dense vectors only. The sparse retrieval capability was introduced in the mGTE multilingual variant (`gte-multilingual-base`), not in gte-large or gte-large-en-v1.5.

---

## 4. Deployment & Infrastructure

### Self-hosted feasibility

**thenlper/gte-large (original, ~335M params):**

| Precision | Approximate VRAM |
|---|---|
| FP32 | ~1.3 GB |
| FP16 | ~0.67 GB |
| INT8 | ~0.35 GB |

Model file size is 0.67 GB (FP16 safetensors). Per HuggingFace automated memory calculations, the largest layer in FP16 is ~59.61 MB, making minimum VRAM around 70 MB for a single forward pass; however, practical batch inference with reasonable batch sizes requires 1–2 GB.

**Alibaba-NLP/gte-large-en-v1.5 (434M params):**

| Precision | Approximate VRAM |
|---|---|
| FP16 | ~0.9 GB (model weights) |
| INT8 | ~0.5 GB |

Model file is 1.25 GB. Runs comfortably on any modern GPU with 4 GB+ VRAM. CPU inference is feasible given the small size.

- **Recommended GPU:** Any GPU with 4 GB+ VRAM; CPU inference viable. RTX 3060 / A10 or better for production throughput.
- **Inference speed:** Not specifically documented. GTE-Base in CoIR was benchmarked at 7.8 ms per sample (index size 0.3 GB); GTE-Large would be somewhat slower given larger parameter count.

### Managed API availability

- Not available directly as a named managed API endpoint from Alibaba Cloud. Alibaba Cloud's managed embedding API (`text-embedding-v3`, `text-embedding-v4`) is powered by a separate GTE-based model not identical to the open-source `gte-large`.
- Available via DeepInfra: https://deepinfra.com/thenlper/gte-large (pay-per-use, pricing not confirmed in research)
- Available via Databricks Marketplace as a packaged model.

### Framework support

| Framework | Status |
|---|---|
| sentence-transformers | Supported |
| HuggingFace Transformers | Supported |
| ONNX | Supported (listed in model card) |
| OpenVINO | Supported (listed in model card) |
| Safetensors | Supported |
| GGUF (community) | Available via community conversions |
| TensorRT | Not officially documented |

---

## 5. Code Retrieval Suitability

**Strengths for code retrieval:**
- Very lightweight — negligible VRAM; easy to deploy anywhere.
- Strong general text retrieval (BEIR rank #2 for GTE-Base-scale models at time of CoIR paper).
- Excellent framework compatibility — works out of the box with sentence-transformers, no custom code required.
- v1.5 provides 8192-token context, which can handle substantial code files.
- MIT license (original) is maximally permissive.

**Weaknesses for code retrieval:**
- 512-token limit in the original version is a hard constraint — most real-world functions or code files exceed this.
- No instruction-tuning — cannot prepend "Represent this code for retrieval" type prefixes to improve code-specific performance.
- English-only — no understanding of multilingual comments or documentation.
- GTE-Base ranked 6th of 9 in CoIR; GTE-Large is expected to be similar relative ranking given no code-specific training.
- Fixed 1024-dim output, no Matryoshka support, limits flexibility.
- No sparse retrieval — cannot participate in hybrid BM25+dense pipelines.

**Comparison to code-specialized models:**
- Voyage-Code-002 averaged 56.26 on CoIR vs GTE-Base's 36.75 — approximately 53% better on code tasks.
- E5-Mistral (55.18) and BGE-M3 also outperform GTE-Base substantially on code retrieval.
- Code-specialized models (Voyage-Code-002, UniXcoder, CodeSage) all outperform GTE on code-specific tasks. The capability gap is significant, not marginal.

**Multi-language code support:** No explicit evaluation data. Given English-only training and no code-specific training, coverage of non-English code comments is poor.

---

## 6. Overall Assessment

- **Recommendation:** Not recommended for production code retrieval
- **Best use case within Kenjutsu:** At best, a lightweight fallback or baseline for non-code text retrieval (PR descriptions, commit messages) where the 512-token limit is acceptable. The v1.5 variant with 8192-token context is meaningfully better for document-length inputs.
- **Key trade-offs:** Extremely low resource cost, broad framework support, and permissive licensing come at the cost of poor code retrieval performance and missing capabilities (no MRL, no instructions, no sparse retrieval, English only). The model was not designed for code and shows it in code-specific benchmarks.
