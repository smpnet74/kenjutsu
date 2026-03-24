# Cohere embed-v4 — Embedding Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-122

---

## 1. Model Identity

| Property | Value |
|---|---|
| Full name | embed-v4 (Embed Multimodal v4) |
| Organization | Cohere |
| Release date | April 15, 2025 |
| Architecture | Proprietary (not disclosed); multimodal (text + images) |
| Parameters | Not disclosed |
| License | Proprietary (API access; private deployment via enterprise agreement) |

## 2. Technical Specifications

| Property | Value |
|---|---|
| Context window | 128,000 tokens (128K) |
| Default dimensions | 1,536 |
| Flexible dimensions | 256, 512, 1,024, 1,536 (Matryoshka) |
| Matryoshka support | Yes — 4 native dimension options |
| Binary quantization | Yes — native; supports float, int8, uint8, binary, ubinary output types |
| int8 quantization | Yes — native (3.66x speedup, minor accuracy loss) |
| Multimodal | Yes — text + images in single embedding space (PNG, JPEG, WebP, GIF) |

### Quantization Performance

| Configuration | Effect |
|---|---|
| int8 | 3.66x average speedup vs float32 |
| Binary | 24.76x average speedup |
| Matryoshka + binary | Up to 83% storage reduction |
| 1,024 dims retention | ~98.5% of full accuracy |
| 512 dims retention | ~95.2% |
| 256 dims retention | ~89.1% |

## 3. Benchmark Performance

### General

| Benchmark | Score |
|---|---|
| MTEB overall | 65.2–66.8 (variance across sources) |
| MTEB retrieval (nDCG@10) | 55.1 |
| MTEB classification | 74.2 |
| Multilingual English MTEB | 68.2 |

### vs Predecessors

| Dataset (BeIR) | embed-v3 | embed-v4 | Delta |
|---|---|---|---|
| NQ | 52.8 | 56.3 | +6.6% |
| HotpotQA | 63.2 | 67.1 | +6.2% |
| FEVER | 75.3 | 79.8 | +6.0% |
| Climate-FEVER | 23.1 | 28.4 | +22.9% |
| SciFact | 66.2 | 71.8 | +8.5% |

### Code-Specific

**No dedicated code retrieval benchmarks published.** Cohere does not report CoIR, CodeSearchNet, or code-specific MTEB scores for embed-v4. The model is positioned for "real-world noisy data" enterprise use cases rather than code-specific retrieval.

### Cross-Lingual

35% improvement over embed-v3 on cross-lingual retrieval. Supports 100+ languages (human languages, not programming).

## 4. Code Retrieval Capabilities

- **NL → code:** Not specifically designed or benchmarked for code. Code is treated as text.
- **Code → code:** Not specifically designed or benchmarked.
- **Cross-language:** Excellent for human languages (100+); not designed for cross-programming-language retrieval.
- **Languages supported:** 100+ human languages. No programming language specialization.

### Multimodal Capability

Unique among models in this evaluation: embed-v4 can embed **interleaved text + images** in a single request. This could be relevant for:
- PR screenshots and visual documentation
- Architecture diagrams alongside code
- UI component embedding for visual review

## 5. Deployment & Cost

| Property | Value |
|---|---|
| API pricing | $0.12/1M text tokens; $0.47/1M image tokens |
| Self-hosted | Enterprise private deployment (contact sales); not open-source |
| GPU requirements | N/A for API |
| Latency | Not independently benchmarked (embed-v4 is recent); Cohere API generally performant |
| Available on | Cohere API, AWS SageMaker, Azure AI Foundry, Oracle OCI, GitHub Models |

**Important:** embed-v3 and embed-v4 embeddings are **incompatible** — migration requires full corpus re-embedding.

## 6. Kenjutsu Fit (1-5)

| Criterion | Score | Notes |
|---|---|---|
| Code retrieval quality | 2 | No code-specific benchmarks; general-purpose model not optimized for code |
| Context window adequacy | 5 | 128K tokens — can embed entire files, multi-file contexts, even small repos |
| Deployment flexibility | 3 | API + enterprise private deployment; no open weights |
| Cost efficiency | 3 | $0.12/1M competitive but not the cheapest; image tokens add up |
| Dimension flexibility | 5 | Excellent Matryoshka (4 sizes) + full native quantization support |
| Ecosystem maturity | 4 | Well-integrated with major cloud providers and vector DBs |

## 7. Verdict

- **Recommendation:** **Viable alternative for non-code content** — not recommended as primary code embedding model
- **Best use case:** If Kenjutsu adopts a multi-model strategy, embed-v4 could handle natural language content (documentation, issue descriptions, PR comments, architecture docs) while a code-specialized model handles code. The 128K context window and multimodal capability are unique advantages for embedding long documents and visual content.
- **Key risk:** No demonstrated code retrieval capability. Using embed-v4 for code search would be suboptimal compared to models specifically trained on code. The lack of published code benchmarks is a red flag — if the model performed well on code, Cohere would likely advertise it.
- **Unique value:** The multimodal embedding (text + images in one space) is not available from any other model in this evaluation. If visual content is important to Kenjutsu's review pipeline, embed-v4 is the only option that can natively handle it.
