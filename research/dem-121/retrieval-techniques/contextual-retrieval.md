# Contextual Retrieval (Anthropic Approach)

## Overview
- **Category:** Chunking / embedding strategy
- **Key papers/implementations:** "Introducing Contextual Retrieval" — Anthropic (September 2024). Built on the observation that chunks lose document-level context when embedded in isolation. Production-validated by Anthropic with reported 49% reduction in retrieval failure rate (67% when combined with BM25).
- **Maturity:** Early production — published by Anthropic with production benchmarks; concept is simple and reproducible; no framework provides it as a first-class feature yet

## How It Works

Contextual retrieval prepends document-level context to each chunk before embedding, so that every chunk carries enough background for its embedding to be meaningful in isolation. This is done via a lightweight LLM call at indexing time.

**Process:**
```python
# For each chunk in a document
for chunk in document.chunks:
    # Step 1: Generate context using LLM with full document
    context = llm.generate(f"""
        <document>
        {document.full_text}
        </document>
        Here is the chunk we want to situate within the whole document:
        <chunk>
        {chunk.text}
        </chunk>
        Please give a short succinct context to situate this chunk within
        the overall document for the purposes of improving search retrieval
        of the chunk. Answer only with the succinct context and nothing else.
    """)
    # Output: "This chunk is from the authentication module's middleware
    # implementation. It handles JWT token validation for the /api/* routes."

    # Step 2: Prepend context to chunk
    enriched_chunk = f"{context}\n\n{chunk.text}"

    # Step 3: Embed the enriched chunk
    embedding = embed(enriched_chunk)

    # Step 4: Store enriched text for BM25 too
    bm25_index.add(enriched_chunk)
```

**Key insight from Anthropic:** The context prepended to each chunk serves two purposes:
1. **Dense embedding improvement**: The embedding captures the chunk's role within the larger document
2. **BM25 keyword enrichment**: The context adds keywords and terms from the broader document that make the chunk findable via lexical search

**Prompt caching optimization:** Anthropic recommends using prompt caching for the document context — the full document is sent with every chunk but cached after the first call, reducing cost by ~90% for multi-chunk documents.

**Reported results (Anthropic benchmarks):**
- Contextual embeddings alone: 35% reduction in retrieval failure rate
- Contextual embeddings + BM25: 49% reduction
- Contextual embeddings + BM25 + reranking: 67% reduction

## Relevance to Code Retrieval
- **Applicable to Kenjutsu?** Yes — code chunks lose critical context when isolated (file purpose, module role, class relationships)
- **Which pipeline stage?** Indexing (document enrichment before embedding)
- **Complementary or replacement?** Complementary — enriches chunks; all retrieval techniques still apply

### Code-Specific Strengths
- **File-level context propagation**: A helper function `_validate_input(data)` embedded alone is ambiguous. With context: "This is a private validation helper in the user registration module, called by `register_user()` to validate form data before database insertion." — now it's precisely searchable.
- **Module role awareness**: Code files have roles within a larger architecture (controller, service, model, utility). Contextual retrieval can surface this role in each chunk's context.
- **Import/dependency context**: Instead of the chunk losing awareness of what libraries it uses (imports at file top, chunk at file bottom), the context can mention key dependencies.
- **BM25 boost**: The generated context adds descriptive terms that BM25 can match — "authentication," "JWT," "middleware" — even if the chunk's raw code only contains `token = request.headers.get('Authorization')`.

### Code-Specific Limitations
- **LLM cost at indexing time**: Similar to code-to-NL translation — every chunk requires an LLM call. Prompt caching helps significantly (document sent once per file, context generated per chunk).
- **Context quality depends on document quality**: If the "document" is a 2000-line God file with no clear structure, the generated context may be vague. Works best with well-structured code.
- **Overlap with code-to-NL translation**: Both techniques use an LLM at indexing time to enrich chunks. Combining them adds cost with potentially diminishing returns — evaluate which provides more value.
- **Context window limits**: The full document must fit in the LLM's context window alongside the chunk and prompt. Very large files may need truncation or hierarchical summarization.

## Known Implementations
- **Custom / DIY** — Anthropic's blog provides the exact prompt; implementation is ~30 lines of Python wrapping an LLM call + chunk processing
- **LlamaIndex** — no first-class "contextual retrieval" node; can be approximated using `SummaryExtractor` or custom `TransformComponent`
- **LangChain** — no native implementation; achievable via custom document transformer
- **Anthropic API** — prompt caching feature specifically supports this use case; beta caching available

## Trade-offs

### Pros
- **Largest single-technique retrieval improvement** reported by Anthropic (35-67% failure rate reduction)
- **Improves both dense and BM25** — the context enriches keyword matching AND semantic embedding, unlike techniques that only help one
- **Simple concept** — prepend context to chunks; no new models, no architectural changes
- **Preserves original chunk text** — context is additive; the chunk's original content is unchanged for generation/display
- **Prompt caching reduces cost** — per-document caching means cost scales with chunks-per-document, not total tokens

### Cons
- **LLM cost at indexing time** — even with caching, large codebases (100K+ chunks) incur significant cost
- **Indexing latency** — LLM calls add seconds per chunk; must be parallelized and batched
- **Context quality varies** — LLM may generate vague or incorrect context; quality monitoring needed
- **Redundant with code-to-NL?** — both enrich chunks with LLM-generated NL content; the marginal value of doing both may not justify the doubled LLM cost
- **Staleness on code changes** — context must be regenerated when code changes; requires tracking chunk-level changes
- **Complexity cost:** Medium — the LLM call is simple; operational complexity (cost, latency, freshness) is the challenge

## Composability

| Technique | Compatible? | Notes |
|-----------|------------|-------|
| Hybrid BM25 + dense | Yes, excellent | Anthropic's own recommendation; enriched context improves both retrieval paths |
| Code-to-NL translation | Partially redundant | Both add LLM-generated NL to chunks; choose one or carefully design prompts to be complementary |
| Late chunking | Partially redundant | Both inject document context into chunk embeddings; late chunking does it via attention, contextual retrieval via text prepending |
| Reranking | Yes | Anthropic showed reranking on top adds significant further improvement (49% → 67%) |
| HyDE | Yes | Contextual retrieval enriches documents; HyDE enriches queries — complementary |
| Matryoshka / quantization | Yes | Standard embedding post-processing applies to enriched chunk embeddings |
| Parent-child retrieval | Partially redundant | Both address "chunk lacks document context"; combining may be excessive |

## Verdict for Kenjutsu
- **Recommendation:** EVALUATE
- **Priority:** Layer 2 — benchmark against code-to-NL translation; adopt whichever provides better quality-per-dollar
- **Rationale:** Contextual retrieval is the most evidence-backed chunk enrichment technique available, with Anthropic's 67% failure rate reduction being the strongest published result. However, its overlap with code-to-NL translation means Kenjutsu should evaluate both head-to-head rather than adopting both. The key comparison: code-to-NL generates a summary of what the code does (intent-focused), while contextual retrieval generates the chunk's role within the document (context-focused). For code, intent-focused summaries may be more valuable for NL queries, but context-focused enrichment may be more valuable for navigation queries ("find where user validation happens in the auth module"). Recommendation: run a controlled evaluation comparing (a) code-to-NL only, (b) contextual retrieval only, (c) combined, on Kenjutsu's target query distribution, then adopt the winner.
