# BGE-large-en-v1.5

**Researched:** 2026-03-23
**Source ticket:** DEM-123

---

## 1. Model Overview

- **Model name:** BGE-large-en-v1.5
- **Provider / Organization:** Beijing Academy of Artificial Intelligence (BAAI)
- **Release date:** September 12, 2023
- **Architecture:** Encoder-only transformer; BERT-large base, bi-encoder (dense retriever)
- **Parameters:** 335M
- **Dimensions:** 1024 (fixed; no native Matryoshka/variable-dimension support)
- **Max context window:** 512 tokens
- **License:** MIT (free for commercial use)
- **Category:** General-purpose with code capability

---

## 2. Benchmark Performance

### MTEB Scores (56-task English benchmark)

| Task category | Score |
|---|---|
| **Overall average** | **64.23** |
| Retrieval (15 tasks) | 54.29 |
| Classification (12 tasks) | 75.97 |
| Clustering (11 tasks) | 46.08 |
| STS (10 tasks) | 83.11 |
| Pair Classification (3 tasks) | 87.12 |
| Reranking (4 tasks) | 60.03 |
| Summarization (1 task) | 31.61 |

At release (September 2023), this was the #1 overall score on the English MTEB leaderboard. It has since been surpassed by newer models.

### Code-Specific Benchmarks

**CoIR (Code Information Retrieval) benchmark — nDCG@10:**
BGE-large-en-v1.5 does not appear on the CoIR leaderboard. The closely related BGE-base-en-v1.5 (110M params, 768-dim) does appear and serves as the best available proxy:

| Task | BGE-base-en-v1.5 | BGE-M3 (for comparison) |
|---|---|---|
| APPS | 4.05 | 7.37 |
| CosQA | 32.76 | 22.73 |
| Synthetic Text2SQL | 45.59 | 48.76 |
| CodeSearchNet | 69.60 | 43.23 |
| CodeSearchNet-CCR | 45.56 | 47.55 |
| CodeTrans-Contest | 38.50 | 47.86 |
| CodeTrans-DL | 21.71 | 31.16 |
| StackOverflow QA | 73.55 | 61.04 |
| CodeFeedback-ST | 64.99 | 49.94 |
| CodeFeedback-MT | 31.42 | 33.46 |
| **Average** | **42.77** | **39.31** |

For context, the top code-specialized models on CoIR: Voyage-Code-002 averages 56.26 and E5-Mistral averages 55.18. BGE-base-en-v1.5 ranked 9th on the leaderboard when the paper was published.

No direct CodeSearchNet or CoSQA standalone benchmark scores for BGE-large-en-v1.5 are published by BAAI. No code-specific training was performed.

---

## 3. Technical Capabilities

- **Matryoshka Representation Learning (MRL):** Not supported. Fixed 1024-dimensional output only. Community fine-tuned variants (e.g., "bge-base-financial-matryoshka") exist but are not official BAAI releases.
- **Quantization support:** Yes. 14 quantized variants available on HuggingFace. Supports FP16, INT8, INT4 inference. INT8 and INT4 are inference-only (no Adam training support).
- **Instruction-tuned:** Yes, for query side only. Query instruction: `"Represent this sentence for searching relevant passages:"`. No instruction needed for passages/documents. This is a lightweight prompt prefix, not RLHF-style instruction tuning.
- **Multi-lingual support:** English only. For multilingual use, BAAI recommends BGE-M3.
- **Sparse + dense hybrid retrieval:** Dense only (bi-encoder). No sparse/lexical retrieval capability. For hybrid, use BGE-M3.

---

## 4. Deployment & Infrastructure

### Self-hosted feasibility

| Precision | Model weight size | Inference VRAM (weights only) | Largest single layer |
|---|---|---|---|
| FP32 | 1.25 GB | ~1.25 GB | 119.23 MB |
| FP16 / BF16 | 639 MB | ~639 MB | 59.61 MB |
| INT8 | 320 MB | ~320 MB | 29.81 MB |
| INT4 | 160 MB | ~160 MB | 14.90 MB |

Add ~20% overhead for activations during inference. At FP16 the model fits comfortably in 1–2 GB VRAM. A single consumer GPU (e.g., RTX 3060 12 GB) can run this at large batch sizes.

Model size on disk: ~1.34 GB (FP32 safetensors).

### Managed API availability

| Provider | Price | Notes |
|---|---|---|
| Together AI | $0.02 / 1M tokens | Input and output both billed at $0.02 |
| DeepInfra (via OpenRouter) | $0.005 / 1M input tokens | Output free |
| Cloudflare Workers AI | $0.20 / 1M input tokens | OpenAI-compatible `/v1/embeddings` endpoint |
| HuggingFace Inference API | Available | Pricing per HF tier; free tier rate-limited |

### Framework support

- sentence-transformers (primary)
- HuggingFace Transformers (`AutoModel` / `AutoTokenizer`)
- FlagEmbedding (`FlagModel`)
- LangChain (`HuggingFaceBgeEmbeddings`)
- ONNX (via `optimum.onnxruntime.ORTModelForFeatureExtraction`, ONNX weights in PR branch)
- text-embeddings-inference (TEI)
- infinity_emb (Infinity deployment server)
- Safetensors format

---

## 5. Code Retrieval Suitability

### Strengths for code retrieval
- Strong general English retrieval (MTEB retrieval: 54.29) — performs well on natural-language-to-code queries (e.g., docstring search, StackOverflow QA)
- Lightweight relative to larger models: 335M params fits easily in low-VRAM environments
- 5.99M monthly HuggingFace downloads; well-tested in production RAG pipelines
- MIT license: no commercial restrictions
- Extensive framework and deployment ecosystem

### Weaknesses for code retrieval
- 512-token context window is a hard constraint: functions exceeding ~400 lines of code will be truncated. Larger files require chunking strategies.
- No code-specific training: not trained on CodeSearchNet, GitHub code corpora, or similar. The model has no concept of code syntax, semantics, or language-specific idioms.
- Fixed 1024-dim only: no MRL support for cost/quality trade-offs at query time
- English only: no cross-lingual retrieval (e.g., code with Spanish comments won't match English queries well)
- Dense retrieval only: misses exact identifier/token matches that sparse retrieval captures (e.g., searching for a specific function name)

### Comparison to code-specialized models
Based on CoIR data using the proxy BGE-base-en-v1.5:
- BGE-base-en-v1.5 (42.77 avg) vs Voyage-Code-002 (56.26 avg): a ~13-point gap
- BGE-base-en-v1.5 (42.77 avg) vs E5-Mistral (55.18 avg): a ~12-point gap
- BGE-M3 itself underperforms BGE-base-en-v1.5 on code tasks (39.31 vs 42.77 avg), which the CoIR paper attributes to distribution mismatch between code and general text data
- BGE-large-en-v1.5 may modestly outperform BGE-base-en-v1.5 on code due to larger capacity, but no direct data is available; the 512-token limit is a shared constraint

### Multi-language code support
No language-specific code training. Works on English-comment-heavy code of any programming language as long as the natural language portions are the primary retrieval signal.

---

## 6. Overall Assessment

**Recommendation:** Worth considering (with caveats)

**Best use case within Kenjutsu:**
- Retrieval over PR descriptions, commit messages, issue bodies, and code comments — general English text where it excels
- A low-cost baseline for benchmarking; useful to quantify how much code-specialized models actually improve on a strong general model
- Self-hosted retrieval in memory-constrained environments (e.g., <2 GB VRAM)

**Key trade-offs:**

| What you gain | What you give up |
|---|---|
| Mature, well-supported model | No code-specific training |
| Lowest self-hosting VRAM footprint (~640 MB FP16) | Hard 512-token limit — problematic for larger code units |
| Very cheap managed API ($0.005/1M via DeepInfra) | No hybrid sparse+dense retrieval |
| Strong general retrieval and STS | No MRL / variable dimensions |
| MIT license | ~13-point code retrieval gap vs best code-specialized models |

---

## Sources

- [BAAI/bge-large-en-v1.5 — HuggingFace model card](https://huggingface.co/BAAI/bge-large-en-v1.5)
- [BGE v1 & v1.5 — BGE official docs](https://bge-model.com/bge/bge_v1_v1.5.html)
- [Memory requirements — HuggingFace discussion #20](https://huggingface.co/BAAI/bge-large-en-v1.5/discussions/20)
- [CoIR benchmark paper (arXiv:2407.02883)](https://arxiv.org/html/2407.02883v1)
- [CoIR leaderboard](https://archersama.github.io/coir/)
- [Together AI model page](https://www.together.ai/models/bge-large-en-v1-5)
- [OpenRouter pricing](https://openrouter.ai/baai/bge-large-en-v1.5)
- [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/models/bge-large-en-v1.5/)
- [C-Pack paper (arXiv:2309.07597)](https://arxiv.org/abs/2309.07597)
