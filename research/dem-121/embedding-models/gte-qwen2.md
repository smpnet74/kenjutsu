# GTE-Qwen2 (Alibaba-NLP/gte-Qwen2-7B-instruct and gte-Qwen2-1.5B-instruct)

**Researched:** 2026-03-23
**Source model cards:**
- https://huggingface.co/Alibaba-NLP/gte-Qwen2-7B-instruct
- https://huggingface.co/Alibaba-NLP/gte-Qwen2-1.5B-instruct
**Paper:** Same GTE paper lineage (arXiv:2308.03281); mGTE extension (arXiv:2407.19669)

---

## 1. Model Overview

Two sizes are available. Both are covered here; the 7B is the flagship and primary focus.

| Property | gte-Qwen2-7B-instruct | gte-Qwen2-1.5B-instruct |
|---|---|---|
| Provider / Organization | Alibaba-NLP (Alibaba Group) | Alibaba-NLP (Alibaba Group) |
| Release date | June 16, 2024 | June 2024 (same release batch) |
| Architecture | Decoder-only LLM (Qwen2-7B base) with bidirectional attention and last-token pooling | Decoder-only LLM (Qwen2-1.5B base) with bidirectional attention and last-token pooling |
| Parameters | 7.6B | 1.5B |
| Dimensions | 3584 | 1536 |
| Max context window | 32,000 tokens | 32,000 tokens |
| License | Apache 2.0 | Apache 2.0 |
| Category | General-purpose with code capability, instruction-tuned | General-purpose with code capability, instruction-tuned |

**Architecture note:** Unlike encoder-only models (BERT-family), gte-Qwen2 models are built on a decoder-only LLM backbone (Qwen2) with bidirectional attention added for embedding tasks. Pooling uses the last token representation. This enables the 32k context window but means the model requires more VRAM than BERT-scale encoders. Instruction tuning is applied to the query side only (documents are encoded without task prefix).

---

## 2. Benchmark Performance

### MTEB Scores — gte-Qwen2-7B-instruct

**English MTEB (56 tasks):**

| Task Category | Score |
|---|---|
| Overall mean (task-level) | 70.72 |
| Overall mean (type-level) | 65.77 |
| Retrieval (15 tasks) | 58.09 |
| Classification (12 tasks) | 88.52 |
| Clustering (11 tasks) | 58.97 |
| STS / Semantic Textual Similarity (10 tasks) | 82.69 |
| Pair Classification (3 tasks) | 85.90 |
| Reranking (4 tasks) | 50.47 |

Note: Ranked #1 English MTEB and #1 Chinese MTEB at time of release (June 16, 2024). As of research date (March 2026), superseded by later models (Qwen3-Embedding, etc.) but remains competitive.

**C-MTEB Chinese (35 tasks):**

| Task Category | Score |
|---|---|
| Overall mean (task-level) | 71.62 |
| Overall mean (type-level) | 72.19 |
| Retrieval | 75.70 |
| Classification | 75.77 |
| Clustering | 66.06 |
| STS | 65.20 |
| Pair Classification | 81.16 |
| Reranking | 69.24 |

**Multilingual MTEB:**
- MTEB-fr (French, 26 tasks): 68.25
- MTEB-pl (Polish, 26 tasks): 67.86

### MTEB Scores — gte-Qwen2-1.5B-instruct

| Benchmark | Score |
|---|---|
| MTEB English (56 tasks) | 67.16 |
| C-MTEB Chinese (35 tasks) | 67.65 |
| MTEB-fr (French, 26 tasks) | 66.60 |
| MTEB-pl (Polish, 26 tasks) | 64.04 |

Task-level breakdown for 1.5B not published on model card.

### Code-Specific Benchmarks

**GTE-Qwen2-7B-instruct on CoIR:** Not available. The CoIR benchmark paper (arXiv:2407.02883, ACL 2025) evaluated GTE-Base but was published before the Qwen2-based models were released in June 2024 (the paper's evaluation set predates the 7B instruct model). No subsequent published CoIR results for gte-Qwen2-7B were located.

**GTE-Qwen2-1.5B-instruct on CoIR:** Not available. Same timing issue.

**CodeSearchNet / CoSQA:** Neither the 7B nor 1.5B model card reports CodeSearchNet or CoSQA scores. No third-party benchmark publications with these scores were located.

**General observations from practitioners:** The model's 32k context window and strong retrieval scores on MTEB suggest meaningful capability for longer code files. However, no peer-reviewed or systematically published code retrieval numbers exist as of this research date.

---

## 3. Technical Capabilities

- **Matryoshka Representation Learning (MRL):** Not explicitly supported or documented on the model card for either 7B or 1.5B. The 1.5B model card previously described 1024-d as default with Matryoshka support for other dimensions, but the current official HuggingFace card and the fetched content do not confirm this for the Qwen2-based models. **Treat as not supported** until confirmed. (Contrast: the newer Qwen3-Embedding family explicitly supports MRL.)
- **Quantization support:**
  - 36 community-quantized variants of 7B on HuggingFace (includes GPTQ, GGUF formats)
  - 21 community-quantized variants of 1.5B on HuggingFace
  - Official GPTQ-quantized 7B: `shuyuej/gte-Qwen2-7B-instruct-GPTQ`
  - GGUF variants: `mav23/gte-Qwen2-7B-instruct-GGUF`
  - No official INT8/INT4 release from Alibaba-NLP directly, but community options are available.
- **Instruction-tuned:** Yes. Query-side instruction tuning using the format: `"Instruct: {task_description}\nQuery: {query}"`. Documents are encoded without prefixes. Pre-built task prompts available in `config_sentence_transformers.json`. This is a meaningful capability for distinguishing query vs. corpus intent.
- **Multi-lingual support:** Yes — the Qwen2 base model covers approximately 30 languages. The embedding model was trained on multilingual corpora. Confirmed benchmark results in English, Chinese, French, and Polish. Qwen2's documented language coverage includes: English, Chinese, Spanish, French, German, Arabic, Russian, Korean, Japanese, Thai, Vietnamese, and ~20 more.
- **Sparse + dense hybrid retrieval:** Not supported. Dense vectors only. No sparse term-weight output. (Sparse retrieval is a capability of the mGTE multilingual encoder variant, not the Qwen2-based decoder models.)

---

## 4. Deployment & Infrastructure

### Self-hosted feasibility

**gte-Qwen2-7B-instruct (7.6B params):**

VRAM requirements are derived from Qwen2-7B base model memory calculations (HuggingFace automated analysis):

| Precision | Model Weights VRAM | Practical Inference VRAM |
|---|---|---|
| FP32 | ~29.84 GB | Not recommended |
| FP16 / BF16 | ~14.92 GB | ~17–18 GB (with 20% overhead) |
| INT8 (GPTQ/bitsandbytes) | ~7.46 GB | ~9 GB |
| INT4 (GPTQ/GGUF) | ~3.73 GB | ~5 GB |

The model card mentions a Docker-based Infinity-emb deployment requiring "16–32 GB VRAM" and NVIDIA Compute Capability >= 8.0 (Ampere or newer: A100, RTX 3090/4090, A10G). The `flash_attn>=2.5.6` requirement means older-generation GPUs may not work without modification.

- **Recommended GPU for FP16:** Single A100 80 GB (comfortable), RTX 4090 24 GB (tight for batching), A10G 24 GB.
- **Recommended GPU for INT8:** RTX 3090 24 GB, A10 24 GB.
- **CPU inference:** Technically possible with quantized GGUF, but impractically slow for production use.

**gte-Qwen2-1.5B-instruct (1.5B params):**

Model file is 6.62 GB (FP32). For inference:

| Precision | VRAM (approximate) |
|---|---|
| FP16 / BF16 | ~3.3 GB |
| INT8 | ~1.7 GB |
| INT4 | ~0.9 GB |

- Runs comfortably on RTX 3060 12 GB or better.
- Feasible on consumer hardware for development; A10/A100 for production throughput.

### Managed API availability

Alibaba Cloud Model Studio offers managed embedding via `text-embedding-v3` and `text-embedding-v4`. These are GTE-based but are **not** identical to the open-source gte-Qwen2 models — they are a separate internal deployment (described as a different GTE variant optimized for the API).

**text-embedding-v3 pricing (Alibaba Cloud Model Studio):**
- ~$0.096 per 1M input tokens (China region)
- ~$0.07 per 1M input tokens (Singapore/Hong Kong region, text-embedding-v4)
- Free quota: 500,000 tokens (90-day trial) for v3; 1M tokens for v4
- Supported dimensions: 512, 768, 1024 (v3); 64–2048 selectable (v4)
- Max input: 8,192 tokens per request
- Note: text-embedding-v4 was released after the gte-Qwen2 open-source models and may be based on a newer GTE variant

**Third-party managed options:**
- The 7B model is available on various inference platforms (Replicate, Together AI, etc.) but pricing was not systematically confirmed in this research.

### Framework support

| Framework | Status |
|---|---|
| sentence-transformers | Supported (`trust_remote_code=True` required) |
| HuggingFace Transformers | Supported (`trust_remote_code=True` required) |
| ONNX | Not officially documented; community conversions may exist |
| Infinity-emb (Docker) | Supported (documented in model card) |
| SWIFT (fine-tuning) | Supported — LoRA-compatible, multi-GPU with DeepSpeed Zero3 |
| vLLM | Likely compatible (Qwen2 architecture is vLLM-supported) |
| TensorRT-LLM | Not officially documented |
| Safetensors | Supported |

**Important:** `trust_remote_code=True` is required for both sentence-transformers and raw transformers usage. This is a non-trivial security consideration for production deployments.

---

## 5. Code Retrieval Suitability

**Strengths for code retrieval:**
- 32,000-token context window can accommodate entire files, multi-file diffs, or long code contexts — a major practical advantage over 512-token encoder models.
- Instruction-tuning allows distinguishing query intent (e.g., "find code that implements X") from document encoding, which can improve precision.
- Strong multilingual capability covers code comments and documentation in ~30 languages.
- High MTEB retrieval scores (58.09 English, 75.70 Chinese) suggest strong general retrieval foundation.
- Apache 2.0 license allows commercial use.
- 32 community-quantized variants lower deployment barrier.

**Weaknesses for code retrieval:**
- No published code-specific benchmark results — performance on code tasks is inferred, not measured.
- VRAM requirements (~15 GB FP16) are substantial compared to encoder-based models (~0.7 GB for gte-large).
- `trust_remote_code=True` requirement introduces supply-chain risk in production.
- No Matryoshka support — fixed 3584-dim embeddings at full cost; cannot tune dimension for cost/latency.
- No sparse retrieval — cannot use hybrid BM25+dense pipelines.
- Slower inference than encoder models due to decoder architecture and larger size.
- Flash attention requirement (Compute Capability >= 8.0) limits GPU compatibility.

**Comparison to code-specialized models:**
- Voyage-Code-002 averaged 56.26 on CoIR; gte-Qwen2-7B has no CoIR results. On general MTEB retrieval, gte-Qwen2-7B scores 58.09 vs Voyage-Code-002's 65+ on code-specific tasks — but these are different benchmarks.
- The model's large context window (32k) is competitive with or exceeds most code-specialized models.
- Without published code retrieval benchmarks, it is impossible to make a definitive comparison. The 7B LLM-based architecture may generalize better to code than smaller encoder models, but this is speculative.

**Multi-language code support:** Strong for documentation and comments in covered languages. No specific evaluation of cross-language code retrieval (e.g., query in English, code in Python/Go/Rust) was found.

---

## 6. Overall Assessment

- **Recommendation (7B):** Worth considering — conditional on VRAM availability and benchmark validation
- **Recommendation (1.5B):** Worth considering as a lower-cost alternative
- **Best use case within Kenjutsu:** Long-context code retrieval where files exceed 512–8192 tokens, multilingual repository support, and cases where query-document distinction via instructions is valuable. The 32k window is genuinely differentiating.
- **Key trade-offs:** The 7B model delivers top-tier MTEB scores and instruction tuning with a 32k context window, but costs ~20x more VRAM than gte-large and has no published code retrieval numbers. The 1.5B offers a middle ground at ~3.3 GB FP16, strong multilingual MTEB, and the same instruction format. Neither model has confirmed code-specific benchmark results — validation testing against CoIR or CodeSearchNet before production deployment is strongly recommended.
