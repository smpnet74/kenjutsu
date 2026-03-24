# Nomic Embed Code — Embedding Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-122

---

## 1. Model Identity

| Property | Value |
|---|---|
| Full name | nomic-embed-code |
| Organization | Nomic AI |
| Release date | March 27, 2025 |
| Architecture | Decoder-based bi-encoder built on Qwen2.5-Coder-7B; last-token pooling |
| Parameters | 7B |
| License | Apache 2.0 (fully open: weights, training data, training code, evaluation code) |

## 2. Technical Specifications

| Property | Value |
|---|---|
| Context window | 32,768 tokens |
| Default dimensions | 3,584 |
| Flexible dimensions | Not documented (no Matryoshka support mentioned) |
| Matryoshka support | No (not documented in model card or paper) |
| Binary quantization | No native support |
| int8 quantization | No native support |

## 3. Benchmark Performance

### General

| Benchmark | Score |
|---|---|
| MTEB overall | Not submitted |
| CoIR average | Not submitted |

### Code-Specific: CodeSearchNet MRR@10

| Language | Nomic Embed Code | Voyage Code 3 | OpenAI text-3-large |
|---|---|---|---|
| Python | **81.7** | 80.8 | 70.8 |
| Java | 80.5 | 80.5 | 72.9 |
| Ruby | 81.8 | **84.6** | 75.3 |
| PHP | **72.3** | 71.7 | 59.6 |
| JavaScript | 77.1 | **79.2** | 68.1 |
| Go | **93.8** | 93.2 | 87.6 |

**Summary:** Nomic Embed Code is competitive with Voyage-code-3, leading on Python, PHP, and Go while trailing on Ruby and JavaScript. Both significantly outperform OpenAI text-embedding-3-large.

## 4. Code Retrieval Capabilities

- **NL → code:** Excellent. Competitive with Voyage-code-3 on CodeSearchNet NL→code retrieval.
- **Code → code:** Expected strong performance given 7B decoder backbone, but no dedicated code→code benchmarks published.
- **Cross-language:** Not specifically benchmarked. Training data covers 6 languages.
- **Languages supported:** 6 programming languages (Python, Java, Ruby, PHP, JavaScript, Go)

### Training Approach

- **Dataset:** CoRNStack — built from The Stack V2 (deduplicated), using function docstring→code pairs
- **Filtering:** Dual-consistency filtering to remove noisy pairs
- **Training:** Contrastive learning with curriculum-based progressive hard negative mining (softmax sampling for increasingly difficult negatives)
- **Minimum docstring length:** 256 tokens (captures long-range dependencies)

## 5. Deployment & Cost

| Property | Value |
|---|---|
| API pricing | ~$0.01/1M tokens via Fireworks AI; Nomic Atlas offers 1M free tokens then Business plan ($40/user/month) |
| Self-hosted | Yes — fully open-source (Apache 2.0); weights on HuggingFace |
| GPU requirements | ~14–16 GB VRAM minimum (7B model at fp16); quantized variants may run on less |
| Latency | 7B models typically 187–221ms per query (independent benchmark for similar-sized models) |

## 6. Kenjutsu Fit (1-5)

| Criterion | Score | Notes |
|---|---|---|
| Code retrieval quality | 5 | Competitive with Voyage-code-3 on CodeSearchNet; 7B model capacity |
| Context window adequacy | 5 | 32K tokens — handles full files and multi-function contexts |
| Deployment flexibility | 5 | Fully open-source (Apache 2.0); self-host anywhere |
| Cost efficiency | 3 | 7B model requires significant GPU; ~$0.01/1M via Fireworks is cheap for API |
| Dimension flexibility | 1 | Fixed 3,584 dimensions; no Matryoshka; no native quantization |
| Ecosystem maturity | 3 | Recent release (March 2025); growing adoption (~72K HF downloads/month) |

## 7. Verdict

- **Recommendation:** **Strong candidate** — especially attractive for self-hosted deployment
- **Best use case:** Primary or secondary code embedding model for teams that require full control over their embedding infrastructure. The Apache 2.0 license and open training data/code make it the most transparent option. Ideal if Kenjutsu wants to avoid vendor lock-in.
- **Key risk:**
  - Fixed 3,584 dimensions with no Matryoshka support means high storage costs at scale (3.5x more storage per vector than Voyage at 1024-dim)
  - 7B model requires substantial GPU for self-hosting
  - Only benchmarked on 6 languages (vs Voyage's 300+)
  - Relatively new (March 2025) — limited production track record
- **Comparison with Voyage-code-3:** Near-parity on code retrieval quality. Nomic wins on openness (Apache 2.0 vs proprietary) and self-hosting flexibility. Voyage wins on dimension flexibility (Matryoshka + quantization), language breadth (300+ vs 6), and ecosystem maturity.
