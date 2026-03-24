# Code-to-NL Translation Before Embedding

## Overview
- **Category:** Embedding strategy / query-document alignment
- **Key papers/implementations:** Greptile engineering blog — reported +12% retrieval improvement from code-to-NL translation before embedding (2024). Related: CodeBERT's bimodal pre-training on NL-code pairs (Feng et al., EMNLP 2020). "Improving Code Search with Hard Negative Mining" — concept of bridging the NL-code vocabulary gap. DocPrompting — Li et al. (ICLR 2023).
- **Maturity:** Early production — Greptile uses in production; technique is straightforward but no standard tooling exists; relies on LLM summarization quality

## How It Works

Code-to-NL translation addresses the **vocabulary mismatch** between how developers describe code in queries (natural language) and what actually exists in the codebase (programming language syntax). The idea: before embedding a code chunk, generate a natural language summary of what the code does, then embed the summary (or concatenate it with the code) instead of raw code alone.

**Pipeline:**
```python
# At indexing time (offline)
for chunk in code_chunks:
    # Step 1: Generate NL description using an LLM
    nl_summary = llm.generate(f"""
        Summarize what this code does in 2-3 sentences.
        Focus on: purpose, inputs/outputs, key behavior.
        Code: {chunk.text}
    """)

    # Step 2: Embed the combined representation
    # Option A: Embed only the summary
    embedding = embed(nl_summary)

    # Option B: Embed summary + code (recommended)
    embedding = embed(f"{nl_summary}\n\n{chunk.text}")

    # Option C: Dual embeddings (store both)
    nl_embedding = embed(nl_summary)
    code_embedding = embed(chunk.text)

    store(chunk.id, embedding, metadata={
        "original_code": chunk.text,
        "nl_summary": nl_summary
    })

# At query time (online) — queries are typically already in NL
query_embedding = embed(user_query)  # no translation needed
results = vector_search(query_embedding, index)
```

**Why it works:** Embedding models — even code-specific ones — are predominantly trained on natural language. When a user asks "function that validates email addresses" and the code defines `def check_email_format(s: str) -> bool`, the NL summary bridges the gap: "Validates whether a string is a properly formatted email address using regex pattern matching."

**Greptile's finding:** +12% retrieval improvement on their production code search benchmark. The improvement was largest for semantic queries ("how does authentication work?") and smallest for exact identifier queries ("where is `parseConfig`?").

## Relevance to Code Retrieval
- **Applicable to Kenjutsu?** Yes — directly addresses the core NL-to-code retrieval challenge
- **Which pipeline stage?** Indexing (document enrichment before embedding)
- **Complementary or replacement?** Complementary — enriches the document representation; all other retrieval techniques still apply

### Code-Specific Strengths
- **Bridges the vocabulary gap**: The #1 challenge in code search — users describe intent in NL, code uses programming syntax. NL summaries align the vocabulary.
- **Embedding model amplification**: Even code-specific embedding models encode NL better than raw code (they're still transformers trained mostly on NL). Giving them NL input plays to their strength.
- **Captures implicit behavior**: Code like `if retries > MAX_RETRIES: raise TimeoutError()` has implicit meaning ("retry logic with timeout") that NL summary makes explicit and searchable.
- **Documentation for undocumented code**: Many codebases lack documentation. LLM-generated summaries provide the "missing docstrings" that make code searchable by intent.

### Code-Specific Limitations
- **LLM cost at indexing time**: Every code chunk requires an LLM call to generate the summary. For a large codebase (100K chunks), this is significant ($50-500 depending on model and chunk size). Batch APIs and smaller models can reduce cost.
- **Summary quality varies**: LLM summaries can be wrong, vague, or miss key aspects. Bad summaries hurt retrieval — "This function processes data" is worse than the raw code.
- **Stale summaries**: When code changes, summaries must be regenerated. Incremental re-indexing must track which chunks changed and regenerate their summaries.
- **Language model dependency**: Ties the indexing pipeline to an LLM — adds latency, cost, and a failure mode (LLM API downtime blocks re-indexing).
- **Diminishes BM25 for code terms**: If you embed only the NL summary, BM25 on the summary loses exact code identifiers. Solution: keep original code in the BM25 index, use NL summary only for the dense embedding.

## Known Implementations
- **Greptile** — production implementation (proprietary); described in engineering blog
- **Custom / DIY** — no framework provides this out-of-the-box; requires: LLM summarization step → concatenation → embedding. ~50 lines of pipeline code.
- **LlamaIndex** — can be approximated using `SummaryExtractor` metadata extractor + `MetadataReplacementPostProcessor`, but not a first-class "code-to-NL" feature
- **Docify / AI docstring generators** — tools that generate docstrings can be repurposed for indexing-time NL generation

## Trade-offs

### Pros
- **Proven retrieval improvement** — +12% in production (Greptile); conceptually sound and validated
- **Stacks with everything** — the enriched text is just a better document for any embedding model or retrieval technique
- **No specialized model needed** — uses existing LLMs (GPT-4o-mini, Claude Haiku, Llama 3) for summarization; no training required
- **Dual benefit**: NL summaries improve both dense retrieval (better embeddings) and can be stored as metadata for display/explanation

### Cons
- **LLM cost at indexing time** — adds $0.50-5.00 per 1K chunks (model-dependent); significant at scale
- **Indexing latency** — LLM calls add seconds per chunk; must be batched and parallelized
- **Summary quality is a variable** — bad summaries can hurt retrieval; requires quality monitoring or human validation sampling
- **Staleness management** — code changes require summary regeneration; adds complexity to incremental indexing
- **Not useful for code-to-code queries** — when the query IS code (e.g., finding similar implementations), NL translation may not help
- **Complexity cost:** Medium — the LLM call itself is simple; the operational complexity (cost management, staleness, quality monitoring) is the real burden

## Composability

| Technique | Compatible? | Notes |
|-----------|------------|-------|
| Hybrid BM25 + dense | Yes, excellent | Keep original code for BM25 index, use NL-enriched text for dense embedding — best of both worlds |
| Late chunking | Yes | Apply late chunking to the NL-enriched chunks |
| Contextual retrieval | Overlapping | Both add context to chunks before embedding; combining adds LLM cost with potentially diminishing returns |
| HyDE | Yes | Code-to-NL enriches documents; HyDE enriches queries — complementary directions |
| Reranking | Yes | Better first-stage retrieval → better candidate set for reranker |
| Matryoshka / quantization | Yes | Standard embedding post-processing applies to NL-enriched embeddings |

## Verdict for Kenjutsu
- **Recommendation:** ADOPT
- **Priority:** MVP / Layer 2 — implement for the initial indexing pipeline; can start with function-level summaries only
- **Rationale:** Code-to-NL translation addresses the fundamental challenge of NL-to-code retrieval and has production-validated impact (+12%). For Kenjutsu, this is especially important because PR review queries are predominantly natural language ("what changed in the authentication flow?", "are there security issues?") while the indexed content is code. Start with function-level summaries using a cost-effective model (GPT-4o-mini or Claude Haiku), concatenated with original code for dense embedding. Keep original code in the BM25 index untouched. The LLM cost is justified by the retrieval quality improvement, but should be monitored — batch processing during indexing and incremental updates on code changes keep costs manageable.
