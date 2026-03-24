# StarEncoder — Embedding Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-122

---

## 1. Model Identity

| Property | Value |
|---|---|
| Full name | StarEncoder |
| Organization | BigCode Project (ServiceNow / Hugging Face collaboration) |
| Release date | December 2023 |
| Architecture | Encoder-only BERT-style Transformer; 12 layers |
| Parameters | ~125M |
| License | Apache 2.0 |

## 2. Technical Specifications

| Property | Value |
|---|---|
| Context window | 1,024 tokens |
| Default dimensions | 768 |
| Flexible dimensions | No |
| Matryoshka support | No |
| Binary quantization | No |
| int8 quantization | No |

## 3. Benchmark Performance

### General

| Benchmark | Score |
|---|---|
| MTEB overall | Not submitted |
| CoIR average | Not submitted |

### Code-Specific

No standardized code retrieval benchmarks published. Primary benchmark use was **PII detection** (F1 >90% for names, emails, IPs) — reflecting the model's original purpose as a data preprocessing tool for StarCoder training.

On xCodeEval code-to-code retrieval (fine-tuned): ~84% monolingual top-100 accuracy.

### Training

- Trained on **The Stack** (~400B tokens) across 86+ programming languages
- Objectives: Masked Language Modeling (MLM) + Next Sentence Prediction (NSP) + contrastive objectives
- **Key context:** StarEncoder was built to preprocess training data for StarCoder, not as a semantic search engine. Its primary purpose was PII detection and data quality filtering.

## 4. Code Retrieval Capabilities

- **NL → code:** Poor for zero-shot; requires fine-tuning. No published NL→code benchmarks.
- **Code → code:** Moderate with fine-tuning (~84% on xCodeEval). Poor zero-shot.
- **Cross-language:** Potentially broad due to 86+ language training, but no cross-language retrieval benchmarks.
- **Languages supported:** 86+ programming languages (broadest language coverage of any model in this evaluation)

## 5. Deployment & Cost

| Property | Value |
|---|---|
| API pricing | No hosted API |
| Self-hosted | Yes — Apache 2.0; weights on HuggingFace (`bigcode/starencoder`) |
| GPU requirements | Minimal (~125M params); runs on CPU |
| Latency | Very fast; small model |

## 6. Kenjutsu Fit (1-5)

| Criterion | Score | Notes |
|---|---|---|
| Code retrieval quality | 1 | Not designed for retrieval; no zero-shot capability; requires fine-tuning |
| Context window adequacy | 1 | 1,024 tokens is too small for most code chunks |
| Deployment flexibility | 5 | Fully open, tiny model, runs anywhere |
| Cost efficiency | 5 | Free; runs on CPU |
| Dimension flexibility | 1 | Fixed 768-dim; no Matryoshka or quantization |
| Ecosystem maturity | 2 | Niche use case (PII detection); not an embedding search model |

## 7. Verdict

- **Recommendation:** **Not recommended** — not designed for code retrieval
- **Best use case:** PII detection in code training data; potential backbone for fine-tuning if 86+ language breadth is critical. Not a semantic search model.
- **Key risk:** Using StarEncoder as-is for code retrieval would produce poor results. It was designed for a different purpose (training data preprocessing). The 1K context window and lack of retrieval-specific training make it unsuitable for Kenjutsu's pipeline.
- **Historical significance:** Demonstrates the BigCode project's approach to code understanding at scale (86+ languages), but superseded by dedicated code retrieval models.
