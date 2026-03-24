# BGE-M3

**Researched:** 2026-03-23
**Source ticket:** DEM-123

---

## 1. Model Overview

- **Model name:** BGE-M3
- **Provider / Organization:** Beijing Academy of Artificial Intelligence (BAAI)
- **Release date:** February 1, 2024 (paper: arXiv:2402.03216, submitted January 30, 2024)
- **Architecture:** Encoder-only transformer; XLM-RoBERTa base with RetroMAE pre-training extension to 8192 tokens; tri-encoder (dense + sparse + multi-vector ColBERT)
- **Parameters:** 568–569M (568M per NVIDIA NIM model card; 569M per BAAI official docs; 567M per Ollama)
- **Dimensions:** 1024 (dense vectors). Matryoshka truncation supported down to 32 dimensions (see section 3).
- **Max context window:** 8,192 tokens
- **License:** MIT (free for commercial use)
- **Category:** General-purpose with code capability; primary design goal is multilingual and long-document retrieval

---

## 2. Benchmark Performance

### MTEB Scores

BAAI did not report standard MTEB English scores at release, stating the model's goal is multilingual and multi-functional versatility rather than single-language English benchmarking. Partial MTEB results have since been published by the community:

**Retrieval tasks (nDCG@10, partial):**
- ArguAna: 54.04
- CQADupstack Android: 48.4
- CQADupstack Gaming: 55.1
- CQADupstack English: 44.4
- CQADupstack GIS: 37.6
- DBPedia: 39.8
- FiQA2018: 41.4
- NFCorpus: 31.3

**Classification tasks (accuracy):**
- Amazon Polarity: 91.0%
- Banking77: 81.9%
- IMDB: 87.8%
- MTOP Domain: 93.4%
- Emotion: 50.2%

**Clustering tasks (V-measure):**
- Reddit Clustering: 45.5%
- Reddit Clustering P2P: 57.5%
- StackExchange Clustering: 55.6%
- ArXiv P2P: 39.4%

No overall MTEB average score is officially reported by BAAI. Community analysis (March 2024, @Yannael) shows BGE-M3 surpassing OpenAI models in both English and multilingual tasks on their own evaluation, but a comparable 56-task MTEB average has not been published.

### Multilingual / Cross-lingual Benchmarks (from official paper, arXiv:2402.03216)

**MIRACL (18-language multilingual retrieval, nDCG@10):**
- Dense only: 67.8 average
- All methods combined: 70.0 average
- Outperforms: mE5-large (65.4), E5-mistral-7b (62.2)

**MKQA (25-language cross-lingual retrieval, Recall@100):**
- Dense only: 75.1
- All methods combined: 75.5
- Outperforms: mE5-large (70.9), E5-mistral-7b (70.1)

**MLDR (13-language long-document retrieval, nDCG@10):**
- All methods combined: 65.0
- Sparse only: 62.2
- Outperforms: E5-mistral-7b (42.6)

**NarrativeQA (English long-document retrieval, nDCG@10):**
- All methods combined: 61.7
- Outperforms: text-embedding-3-large (51.6), E5-mistral-7b (49.9)

### Code-Specific Benchmarks

**CoIR (Code Information Retrieval) benchmark — nDCG@10 (rank 10 of models evaluated):**

| Task | BGE-M3 | BGE-base-en-v1.5 (proxy) | Voyage-Code-002 (top) |
|---|---|---|---|
| APPS | 7.37 | 4.05 | — |
| CosQA | 22.73 | 32.76 | — |
| Synthetic Text2SQL | 48.76 | 45.59 | — |
| CodeSearchNet | 43.23 | 69.60 | — |
| CodeSearchNet-CCR | 47.55 | 45.56 | — |
| CodeTrans-Contest | 47.86 | 38.50 | — |
| CodeTrans-DL | 31.16 | 21.71 | — |
| StackOverflow QA | 61.04 | 73.55 | — |
| CodeFeedback-ST | 49.94 | 64.99 | — |
| CodeFeedback-MT | 33.46 | 31.42 | — |
| **Average** | **39.31** | **42.77** | **56.26** |

BGE-M3 ranked 10th (last) among evaluated models on CoIR when the paper was published. Notably, it underperforms the smaller BGE-base-en-v1.5 (110M) on average. The CoIR paper attributes this to code data being structurally different from general text — BGE-M3's longer context capability does not compensate for the domain mismatch. On tasks requiring understanding of multi-turn code conversations (CodeFeedback-MT), BGE-M3 is slightly better.

The paper explicitly notes: "models excelling in text retrieval may not necessarily perform well in code retrieval."

No standalone CodeSearchNet MRR or CoSQA accuracy numbers are reported by BAAI for BGE-M3.

---

## 3. Technical Capabilities

- **Matryoshka Representation Learning (MRL):** Supported for dense vectors. Truncation down to 32 dimensions is possible. The model was not natively trained with MRL (not part of the original paper's training objective), but post-training dimension truncation is supported. Some third-party providers (e.g., DeepInfra via OpenRouter) describe MRL from 256 to 2048 dimensions — this refers to truncation of the 1024-dim dense vector, which is a documented capability. Not the same as native MRL training (which would optimize sub-dimension quality explicitly). Use with caution for very small dimensions; accuracy degradation has not been benchmarked by BAAI.

- **Quantization support:** Yes. 77 quantized variants available on HuggingFace.
  - FP16/BF16: fully supported, ~1.06 GB model weights
  - INT8: supported (~541 MB)
  - INT4: supported (~271 MB)
  - Quantized INT8/INT4 are inference-only (no Adam training support)

- **Instruction-tuned:** No formal query instruction prefix is documented for BGE-M3. The model is designed for zero-instruction use across all three retrieval modes. (Contrast with BGE-large-en-v1.5 which uses an explicit query instruction for retrieval tasks.)

- **Multi-lingual support:**
  - 100+ working languages supported
  - Training data covers 170+ languages
  - MIRACL evaluation covers 18 languages; MKQA covers 25 languages
  - Strong bitext mining: German-English 99.5%, French-English 98.7%, Chinese-English 99.1%, Russian-English 97.9% (BUCC F1)

- **Sparse + dense hybrid retrieval:** Yes — this is BGE-M3's primary differentiator. Three modes in a single model:
  1. **Dense retrieval:** normalized [CLS] token embedding; standard bi-encoder
  2. **Sparse/lexical retrieval:** token-level importance weights via linear + ReLU layer (BM25-like, but learned); enables exact keyword matching
  3. **Multi-vector (ColBERT-style):** full output embedding sequence for late-interaction scoring

  Scores from all three modes can be combined with configurable weights (default: `[0.4, 0.2, 0.4]` for dense, sparse, colbert). Hybrid mode consistently outperforms dense-only on MIRACL (+2.2 nDCG@10) and MLDR benchmarks. Native integration with Vespa and Milvus for hybrid retrieval pipelines.

---

## 4. Deployment & Infrastructure

### Self-hosted feasibility

| Precision | Model weight size | Inference VRAM (weights only) | Largest single layer |
|---|---|---|---|
| FP32 | 2.12 GB | ~2.12 GB | 1008.71 MB |
| FP16 / BF16 | 1.06 GB | ~1.06 GB | 504.36 MB |
| INT8 | 541 MB | ~541 MB | 252.18 MB |
| INT4 | 271 MB | ~271 MB | 126.09 MB |

Add ~20% overhead for activations. Practical runtime VRAM with FP16 at batch inference (community-reported):
- batch_size=128, max_length=512: ~5.9 GB VRAM
- batch_size=200, max_length=512: ~7.6 GB VRAM
- batch_size=256, max_length=512: ~9.0 GB VRAM
- batch_size=256, max_length=256: ~5.7 GB VRAM

At max_length=8192 (full context), VRAM usage will be substantially higher due to attention mechanism memory scaling. A 16 GB GPU (e.g., RTX 4080, A4000) is recommended for production use at 8192-token inputs.

Model size on disk: ~2.27 GB (FP32) or ~1.06 GB (FP16).

### Managed API availability

| Provider | Price | Notes |
|---|---|---|
| DeepInfra (via OpenRouter) | $0.01 / 1M input tokens | Output free; fp32 standard variant |
| NVIDIA NIM | Not publicly listed | Available; contact NVIDIA for pricing; TensorRT + Triton backend on L40 |
| Ollama | Free (local) | `bge-m3:567m-fp16` tag available |

BGE-M3 is not listed as a managed offering on Together AI as of this research date. NVIDIA NIM provides it via containerized deployment (`nim/baai/bge-m3` on NGC).

### Framework support

- FlagEmbedding (`BGEM3FlagModel`) — primary, supports all three retrieval modes
- sentence-transformers (dense retrieval only)
- HuggingFace Transformers (`AutoModel`)
- PyTorch
- ONNX
- text-embeddings-inference (TEI)
- Ollama (local self-hosting)
- TensorRT + Triton (via NVIDIA NIM)
- Vespa (hybrid retrieval integration documented)
- Milvus (hybrid retrieval integration documented)
- Safetensors format; 409 fine-tuned variants and 77 quantized variants on HuggingFace

---

## 5. Code Retrieval Suitability

### Strengths for code retrieval
- 8,192-token context window: handles large files, multi-function modules, and long diffs without chunking
- Sparse retrieval mode: captures exact identifier/token matches (function names, API names, keywords) that dense retrieval misses — valuable for code where precise token matching matters
- Hybrid mode (dense + sparse + ColBERT) can be tuned to weight identifier matching more heavily
- 100+ language support covers international codebases with non-English comments and docstrings
- Multilingual sparse retrieval can find code by non-English variable names or comments
- Strong long-document retrieval: NarrativeQA performance (61.7 nDCG@10) demonstrates capability on long structured text
- MIT license, very high download volume (16.1M/month)

### Weaknesses for code retrieval
- Underperforms smaller BGE-base-en-v1.5 on CoIR average (39.31 vs 42.77): larger capacity and longer context do not compensate for lack of code-specific training
- Particularly poor on CosQA (22.73) and CodeSearchNet (43.23) vs BGE-base's 32.76 and 69.60 — substantial drops on the most common code retrieval benchmarks
- ~17-point gap vs top code-specialized models (Voyage-Code-002 avg 56.26)
- Sparse retrieval underperforms in cross-lingual scenarios due to vocabulary mismatch (explicitly noted in paper)
- Higher VRAM footprint than BGE-large-en-v1.5: need 6–9 GB GPU VRAM for practical batch sizes
- No native instruction-tuned query prefix

### Comparison to code-specialized models
BGE-M3 ranked last (10th) among all evaluated models on the CoIR benchmark when the paper was published. Code-specialized models hold a significant lead:
- Voyage-Code-002: 56.26 avg (+16.95 over BGE-M3)
- E5-Mistral: 55.18 avg (+15.87 over BGE-M3)

BGE-M3's advantage over code-specialized models is the 8192-token context window and hybrid retrieval — if the use case involves very long code files or requires exact token matching via sparse retrieval, BGE-M3 may be competitive in scenarios not captured by CoIR's benchmark tasks.

### Multi-language code support
No code-specific training. Works on code in any human language when the retrieval signal is in the natural language portions (comments, docstrings). The multilingual capability is for human language, not programming language diversity.

---

## 6. Overall Assessment

**Recommendation:** Worth considering (for specific use cases only)

**Best use case within Kenjutsu:**
- Long-file retrieval: BGE-M3's 8192-token window is the decisive advantage when full-file or multi-function context must be embedded without chunking
- Hybrid keyword + semantic search: sparse retrieval captures exact function/class name matches that pure dense models miss — useful when engineers search by identifier
- Multilingual codebases: repos with mixed-language comments or non-English documentation
- Not recommended as the primary code retrieval model: CoIR results show it is outperformed even by smaller general-purpose models on most code benchmarks

**Key trade-offs:**

| What you gain | What you give up |
|---|---|
| 8,192-token context window | Poorest code retrieval accuracy of evaluated models (CoIR avg 39.31) |
| Hybrid dense+sparse+ColBERT retrieval | No code-specific training |
| 100+ language support | Higher VRAM (6–9 GB for practical batches) |
| Native Milvus/Vespa hybrid integration | More complex deployment than single-mode models |
| MIT license | ~17-point gap vs best code-specialized models |
| Strong multilingual benchmarks (MIRACL, MKQA) | Sparse retrieval fails in cross-lingual scenarios |

---

## Sources

- [BAAI/bge-m3 — HuggingFace model card](https://huggingface.co/BAAI/bge-m3)
- [BGE M3-Embedding paper (arXiv:2402.03216v3)](https://arxiv.org/html/2402.03216v3)
- [BGE-M3 — BGE official docs](https://bge-model.com/bge/bge_m3.html)
- [Memory requirements — HuggingFace discussion #64](https://huggingface.co/BAAI/bge-m3/discussions/64)
- [MTEB scores — HuggingFace discussion #7](https://huggingface.co/BAAI/bge-m3/discussions/7)
- [CoIR benchmark paper (arXiv:2407.02883)](https://arxiv.org/html/2407.02883v1)
- [CoIR leaderboard](https://archersama.github.io/coir/)
- [NVIDIA NIM model card](https://build.nvidia.com/baai/bge-m3/modelcard)
- [OpenRouter pricing](https://openrouter.ai/baai/bge-m3)
- [Ollama library](https://ollama.com/library/bge-m3)
