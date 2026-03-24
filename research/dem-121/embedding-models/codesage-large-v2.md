# CodeSage-large-v2 — Embedding Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-122

---

## 1. Model Identity

| Property | Value |
|---|---|
| Full name | codesage-large-v2 |
| Organization | Amazon Science / AWS AI Labs (**correction:** not Microsoft as originally noted in task description) |
| Release date | December 2024 (v2); original CodeSage: ICLR 2024 |
| Architecture | Custom encoder architecture ("CodeSage"); StarCoder tokenizer (vocab 49,154); 24 hidden layers, 16 attention heads |
| Parameters | 1.3B |
| License | Apache 2.0 |

## 2. Technical Specifications

| Property | Value |
|---|---|
| Context window | 2,048 tokens |
| Default dimensions | 2,048 |
| Flexible dimensions | Yes — Matryoshka Representation Learning supported |
| Matryoshka support | Yes |
| Binary quantization | No native support |
| int8 quantization | No native support |

**Note:** The "1K context" sometimes cited refers to the embedding dimension of v1's small model (1,024 dims), not a context window limit. The actual context window is 2,048 tokens.

## 3. Benchmark Performance

### General

| Benchmark | Score |
|---|---|
| MTEB overall | Not submitted |
| MTEB retrieval | Not submitted |

### Code-Specific: CoIR Leaderboard (Rank #2 overall)

| Task | nDCG@10 |
|---|---|
| Apps | 50.45 |
| CosQA | 32.73 |
| Synthetic Text2SQL | 59.78 |
| CodeSearchNet | **94.26** |
| CodeSearchNet-CCR | 78.09 |
| CodeTrans-Contest | 85.27 |
| CodeTrans-DL | 33.29 |
| StackOverflow QA | 79.41 |
| CodeFeedBack-ST | 71.32 |
| CodeFeedBack-MT | 57.16 |
| **Average** | **64.18** |

For reference: #1 on CoIR is SFR-Embedding-Code-2B_R at 67.41 average.

### Internal Benchmarks (Code→Code MRR@10)

| Language | MRR@10 |
|---|---|
| Python | 61.11 |
| Java | 47.09 |
| JavaScript | 51.18 |
| TypeScript | 60.67 |
| C# | 28.04 |
| C | 43.40 |
| Ruby | 60.74 |
| PHP | 67.87 |
| Go | 43.86 |
| **Average** | **51.55** |

NL→Code: CoSQA = 53.18, AdvTest = 56.31 (MRR@10).

## 4. Code Retrieval Capabilities

- **NL → code:** Good. 94.26 nDCG@10 on CodeSearchNet (CoIR); competitive NL→code scores.
- **Code → code:** Moderate. 51.55 average MRR@10 across 9 languages — weaker on C# (28.04) and C (43.40).
- **Cross-language:** Not explicitly benchmarked, but multi-language training suggests basic cross-language capability.
- **Languages supported:** 9 (C, C#, Go, Java, JavaScript, TypeScript, PHP, Python, Ruby)

### Training Approach

Two-stage:
1. **Pretraining:** Masked Language Modeling (MLM) + identifier deobfuscation on The Stack V1
2. **Fine-tuning:** Contrastive learning on (docstring, code) pairs from The Stack V2, with consistency filtering that removed ~40% of low-quality pairs

## 5. Deployment & Cost

| Property | Value |
|---|---|
| API pricing | No commercial API available |
| Self-hosted | Yes — Apache 2.0, weights on HuggingFace (`codesage/codesage-large-v2`) |
| GPU requirements | ~3–4 GB VRAM at fp16 (1.3B params); runs on consumer GPUs |
| Latency | Fast for its capability level; 1.3B params is much lighter than 7B models |

**Caveats:**
- Requires `trust_remote_code=True` (non-standard architecture classes)
- Must append EOS token to each tokenized sequence
- Low HuggingFace downloads (~895/month) suggests limited production adoption

## 6. Kenjutsu Fit (1-5)

| Criterion | Score | Notes |
|---|---|---|
| Code retrieval quality | 4 | #2 on CoIR; excellent CodeSearchNet scores; weaker on code→code |
| Context window adequacy | 2 | 2,048 tokens is a significant constraint — many functions exceed this |
| Deployment flexibility | 4 | Fully open-source; lightweight enough for consumer GPU |
| Cost efficiency | 5 | Free; 1.3B runs cheaply; efficient for its quality level |
| Dimension flexibility | 3 | Matryoshka supported; no native quantization |
| Ecosystem maturity | 2 | Low adoption; non-standard loading requirements; no hosted API |

## 7. Verdict

- **Recommendation:** **Viable alternative** — excellent quality-to-size ratio but context window is a hard constraint
- **Best use case:** Self-hosted environments where GPU budget is limited and code chunks are pre-split to <2K tokens. Could serve as a lightweight embedding model for function-level chunks (which typically fit within 2K tokens).
- **Key risk:** The 2,048-token context window is the primary limitation. Multi-function chunks, class definitions, and long functions will be truncated. This makes it unsuitable as a primary model for a pipeline that may need to embed larger code contexts. Low ecosystem adoption raises questions about long-term maintenance.
