# SFR-Embedding — Embedding Model Evaluation

- **Evaluator:** Research Specialist
- **Date:** 2026-03-24
- **Issue:** DEM-122

---

This evaluation covers the SFR-Embedding family from Salesforce, with focus on the **code-specialized variant** (SFR-Embedding-Code / CodeXEmbed) as well as the general-purpose models for context.

---

## Family Overview

| Model | Parameters | Purpose | MTEB/CoIR Score | Release |
|---|---|---|---|---|
| SFR-Embedding-Mistral | 7.11B | General text | MTEB: 67.6 (#1 at launch) | Jan 2024 |
| SFR-Embedding-2_R | 7B | General text | MTEB: ~70+ (#1 at launch) | Jun 2024 |
| SFR-Embedding-Code-400M_R | 400M | Code retrieval | CoIR: 61.89 (#3) | Nov 2024 |
| **SFR-Embedding-Code-2B_R** | **2B** | **Code retrieval** | **CoIR: 67.41 (#1)** | **Nov 2024** |
| SFR-Embedding-Code-7B | 7B | Code retrieval | CoIR: ~67+ (#1 at launch) | Nov 2024 |

---

## Primary Evaluation: SFR-Embedding-Code-2B_R

### 1. Model Identity

| Property | Value |
|---|---|
| Full name | SFR-Embedding-Code-2B_R (CodeXEmbed) |
| Organization | Salesforce AI Research |
| Release date | November 2024 (ICLR 2025 conference paper) |
| Architecture | LLM with bidirectional attention (unlike causal LLMs); contrastive training with hard negatives |
| Parameters | 2B |
| License | CC-BY-NC-4.0 (**non-commercial only**) |

### 2. Technical Specifications

| Property | Value |
|---|---|
| Context window | 4,096 tokens (estimated; Mistral-based family uses 4K) |
| Default dimensions | Not publicly documented |
| Flexible dimensions | No Matryoshka support documented |
| Matryoshka support | No |
| Binary quantization | No native support |
| int8 quantization | No native support |

### 3. Benchmark Performance

#### CoIR Leaderboard — Rank #1 (as of March 2026)

| Task | nDCG@10 |
|---|---|
| Apps | Data not published per-task for 2B |
| CodeFeedBack-ST | 90.54 |
| CodeTrans-Contest | 86.63 |
| **Average** | **67.41** |

#### Capabilities

- Supports **12 programming languages**
- **5 retrieval categories:** code→text, text→code, code→code, text→text, hybrid
- Outperforms NV-Embed-V2 and SFR-V2 on combined text + code retrieval (MTEB/BEIR)
- BEIR average for 7B variant: ~60

### 4. Code Retrieval Capabilities

- **NL → code:** Excellent. #1 on CoIR which includes NL→code tasks.
- **Code → code:** Excellent. Strong on CodeTrans-Contest (86.63) and CodeFeedBack-ST (90.54).
- **Cross-language:** Supported across 12 languages.
- **Languages supported:** 12 programming languages (not enumerated in public docs)

### 5. Deployment & Cost

| Property | Value |
|---|---|
| API pricing | No hosted API from Salesforce |
| Self-hosted | Yes — weights on HuggingFace (CC-BY-NC-4.0) |
| GPU requirements | ~6–8 GB VRAM at float16 (2B params) |
| Latency | Moderate; 2B is significantly faster than 7B variants |

---

## Secondary: SFR-Embedding-Mistral (General-Purpose)

### Key Facts

- **MTEB overall:** 67.6 (was #1 at launch, January 2024)
- **Architecture:** LoRA fine-tuning (rank r=8) on E5-mistral-7b-instruct — only 21M trainable parameters
- **Dimensions:** 4,096
- **Context:** 4,096 tokens
- **License:** CC-BY-NC-4.0
- **GPU:** ~14–16 GB VRAM
- **Latency:** 187–221ms per query (7B class models)
- **Not code-specialized** — included for context only

---

## Kenjutsu Fit (1-5) — SFR-Embedding-Code-2B_R

| Criterion | Score | Notes |
|---|---|---|
| Code retrieval quality | 5 | #1 on CoIR; best code retrieval benchmark score of any model evaluated |
| Context window adequacy | 3 | ~4K tokens; adequate for function-level, tight for file-level |
| Deployment flexibility | 3 | Open weights but **CC-BY-NC-4.0 restricts commercial use** |
| Cost efficiency | 4 | Free to run; 2B is GPU-efficient; but license restricts production use |
| Dimension flexibility | 1 | No Matryoshka; no native quantization |
| Ecosystem maturity | 3 | Strong research backing (ICLR 2025); limited production adoption |

## Verdict

- **Recommendation:** **Strong candidate with critical license constraint** — best code retrieval scores but CC-BY-NC-4.0 blocks commercial deployment
- **Best use case:** If Salesforce grants a commercial license or releases under a permissive license, SFR-Embedding-Code-2B_R would be the top choice for code retrieval quality. The 2B variant offers excellent quality with manageable GPU requirements.
- **Key risk:** **CC-BY-NC-4.0 license prohibits commercial use.** This is a hard blocker for Kenjutsu unless a separate license is negotiated. The 400M variant has the same restriction. This is the most important factor — the model cannot be used in a commercial product without explicit permission from Salesforce.
- **If license is resolved:** The 2B model at 6–8 GB VRAM with #1 CoIR performance would be the optimal balance of quality and efficiency. The 400M variant (61.89 CoIR, runs on consumer GPU) is a lighter alternative.
