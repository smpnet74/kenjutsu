# DEM-121: Evaluation Framework for Non-LLM Models

## Purpose

Standardized evaluation criteria for all embedding and reranking models assessed under DEM-121. Every model evaluation MUST follow this template to enable direct comparison.

---

## Embedding Model Evaluation Template

Each embedding model gets its own file in `research/dem-121/embedding-models/` named `{model-name}.md`.

### Required Sections

```markdown
# {Model Name}

## Overview
- **Provider:** {company/organization}
- **Model ID:** {exact model identifier for API/download}
- **Architecture:** {transformer variant, parameter count}
- **Training approach:** {contrastive, MLM, instruction-tuned, etc.}
- **License:** {MIT, Apache 2.0, proprietary API, etc.}
- **Release date:** {YYYY-MM or approximate}
- **Active maintenance:** {yes/no, last update date}

## Specifications
- **Embedding dimensions:** {default and available options}
- **Max context window:** {tokens}
- **Supported languages:** {programming and natural languages}
- **Matryoshka support:** {yes/no — can dimensions be truncated without re-training?}
- **Binary/scalar quantization support:** {yes/no, quality impact if known}

## Benchmark Performance
- **MTEB overall score:** {if available}
- **MTEB retrieval score:** {specifically retrieval tasks}
- **Code-specific benchmarks:** {CoSQA, CodeSearchNet, SWE-bench retrieval, or similar}
- **Comparison to Voyage-code-3:** {relative performance delta if measurable}

Note: Flag benchmark reliability issues (e.g., CoSQA has ~51% incorrect labels).

## Code Retrieval Suitability
- **Code understanding depth:** {token-level, statement-level, function-level, semantic}
- **Cross-language retrieval:** {can it match Python query to Java implementation?}
- **Natural language → code:** {how well does it handle NL queries against code?}
- **Code → code similarity:** {clone detection, similar function finding}
- **AST/structure awareness:** {does it understand code structure or treat as text?}

## Operational Characteristics
- **Deployment:** {API-only, self-hosted, both}
- **Latency:** {P50/P99 per request if available, batch throughput}
- **Cost:** {per 1M tokens or per request}
- **Batch API support:** {yes/no}
- **Rate limits:** {if API-based}
- **GPU requirements:** {if self-hosted — VRAM, recommended hardware}

## Strengths
- {bullet points}

## Weaknesses
- {bullet points}

## Verdict for Kenjutsu
- **Recommendation:** {STRONG YES / YES / MAYBE / NO / STRONG NO}
- **Best role:** {primary embedding, secondary/specialized, not suitable}
- **Rationale:** {1-2 sentences}
```

---

## Reranking Model Evaluation Template

Each reranking model gets its own file in `research/dem-121/reranking-models/` named `{model-name}.md`.

### Required Sections

```markdown
# {Model Name}

## Overview
- **Provider:** {company/organization}
- **Model ID:** {exact model identifier}
- **Architecture:** {cross-encoder, late interaction, listwise, etc.}
- **Training data:** {MS MARCO, code-specific, mixed}
- **License:** {MIT, Apache 2.0, proprietary API, etc.}
- **Release date:** {YYYY-MM or approximate}

## Specifications
- **Max input length:** {query + document combined tokens}
- **Input format:** {query-document pair, listwise, etc.}
- **Output:** {relevance score range, normalized or raw}
- **Multi-language support:** {yes/no, which languages}

## Benchmark Performance
- **MS MARCO MRR@10:** {if available}
- **BEIR/MTEB reranking scores:** {if available}
- **Code-specific reranking performance:** {if benchmarked}
- **Comparison to cross-encoder baselines:** {relative performance}

## Code Reranking Suitability
- **Handles code syntax:** {does it understand code structure or treat as prose?}
- **Query types tested:** {NL→code, code→code, error→fix}
- **Long document handling:** {how does it handle function-length or file-length inputs?}

## Operational Characteristics
- **Deployment:** {API-only, self-hosted, both}
- **Latency:** {per query-document pair, batch reranking of N candidates}
- **Cost:** {per 1M tokens, per search, or per request}
- **GPU requirements:** {if self-hosted}
- **Candidate limit:** {max documents per reranking call}

## Strengths
- {bullet points}

## Weaknesses
- {bullet points}

## Verdict for Kenjutsu
- **Recommendation:** {STRONG YES / YES / MAYBE / NO / STRONG NO}
- **Best role:** {primary reranker, secondary/specialized, not suitable}
- **Rationale:** {1-2 sentences}
```

---

## Advanced Retrieval Technique Evaluation Template

Each technique gets its own file in `research/dem-121/retrieval-techniques/` named `{technique-name}.md`.

### Required Sections

```markdown
# {Technique Name}

## Overview
- **Category:** {chunking, embedding strategy, search fusion, interaction model}
- **Key papers/implementations:** {citations with dates}
- **Maturity:** {research-only, early production, production-proven}

## How It Works
{2-4 paragraph technical explanation with diagrams/pseudocode if helpful}

## Relevance to Code Retrieval
- **Applicable to Kenjutsu?** {yes/no/partially}
- **Which pipeline stage?** {indexing, query, retrieval, reranking, fusion}
- **Complementary or replacement?** {does it replace existing approach or layer on top?}

## Known Implementations
- {library/framework, maturity, link}

## Trade-offs
- **Pros:** {bullet points}
- **Cons:** {bullet points}
- **Complexity cost:** {low/medium/high — what does adoption require?}

## Verdict for Kenjutsu
- **Recommendation:** {ADOPT / EVALUATE / DEFER / SKIP}
- **Priority:** {MVP / Layer 2 / Layer 3 / Future}
- **Rationale:** {1-2 sentences}
```

---

## Consolidated Assessment Structure

The final `embedding-reranking-assessment.md` will synthesize all individual evaluations into:

1. **Executive Summary** — Top-line recommendations
2. **Embedding Model Tier List** — Ranked with rationale
3. **Reranking Model Tier List** — Ranked with rationale
4. **Retrieval Technique Recommendations** — By pipeline layer
5. **Recommended Pipeline Architecture** — Single vs. multi-model, with specific model selections
6. **Cost-Performance Analysis** — Total pipeline cost modeling
7. **Migration Path** — From current assumptions to recommended stack
8. **Open Questions** — What we still don't know and how to resolve it
