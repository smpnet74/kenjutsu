# Hypothetical Document Embedding (HyDE)

## Overview
- **Category:** Query expansion / embedding strategy
- **Key papers/implementations:** "Precise Zero-Shot Dense Retrieval without Relevance Labels" — Gao et al. (ACL 2023). Implemented in LlamaIndex (`HyDEQueryTransform`), LangChain (`HypotheticalDocumentEmbedder`), and various RAG frameworks.
- **Maturity:** Early production — widely implemented in RAG frameworks; proven effective for NL retrieval; less validated for code-specific use cases

## How It Works

HyDE addresses the **query-document asymmetry** problem: queries are short and vague, while documents are long and detailed. Embedding models produce better representations of documents than of queries because documents contain more context. HyDE exploits this by generating a hypothetical document that would answer the query, then embedding that document instead of the query.

```python
# Standard retrieval
query = "How does the authentication middleware work?"
query_embedding = embed(query)  # short query → weak embedding
results = search(query_embedding)

# HyDE retrieval
query = "How does the authentication middleware work?"

# Step 1: Generate hypothetical answer using LLM
hypothetical_doc = llm.generate(f"""
    Write a detailed passage that would answer this question.
    Question: {query}
""")
# Output: "The authentication middleware intercepts incoming HTTP requests
# and validates JWT tokens in the Authorization header. It extracts the
# token, verifies the signature using the configured secret key, checks
# expiration claims, and attaches the decoded user object to the request
# context. Invalid or expired tokens result in a 401 Unauthorized response..."

# Step 2: Embed the hypothetical document (not the query)
hyde_embedding = embed(hypothetical_doc)

# Step 3: Search — now comparing document-like embedding against documents
results = search(hyde_embedding)
```

**Why it works:** The hypothetical document occupies the same region of embedding space as the actual documents — it's written in the same style, uses the same vocabulary, and has similar length. This creates much better vector similarity than comparing a 10-word query against a 500-word document.

**Multi-hypothesis variant:** Generate N hypothetical documents, embed each, and average the embeddings. This reduces variance from any single LLM generation:
```python
hypothetical_docs = [llm.generate(query) for _ in range(N)]
hyde_embedding = mean([embed(doc) for doc in hypothetical_docs])
```

## Relevance to Code Retrieval
- **Applicable to Kenjutsu?** Partially — effective for NL-intent queries; less useful for code-specific queries
- **Which pipeline stage?** Query processing (transforms the query before embedding)
- **Complementary or replacement?** Complementary — transforms query; all retrieval techniques still apply downstream

### Code-Specific Strengths
- **NL-to-code bridge at query time**: For queries like "retry logic with exponential backoff," the LLM generates hypothetical code that contains the relevant keywords and patterns (`time.sleep`, `2 ** attempt`, `max_retries`) — bridging the vocabulary gap from the query side
- **Handles vague queries well**: PR review queries like "what security issues might exist?" benefit from HyDE generating specific security-related code patterns to search for
- **No indexing cost**: Unlike code-to-NL translation (which runs at indexing time), HyDE runs only at query time — no additional indexing overhead

### Code-Specific Limitations
- **Query-time latency**: Each query requires an LLM call (200-2000ms depending on model). For interactive code search, this may be unacceptable. Mitigated by using fast models (GPT-4o-mini, Claude Haiku) or parallel generation.
- **Hallucinated code patterns**: The LLM may generate plausible but incorrect hypothetical code. If the hypothetical uses `jwt.verify()` but the actual codebase uses a custom `validate_token()` function, the embedding may not match well.
- **Worse for exact identifier queries**: Queries like "where is parseConfig defined?" don't benefit from HyDE — the original query already contains the exact term needed. HyDE adds noise by generating a hypothetical document about config parsing that may not match the actual implementation.
- **BM25 integration is tricky**: HyDE generates a hypothetical document for dense embedding, but the BM25 search should still use the original query (for exact keyword matching). This means HyDE only improves one half of hybrid search.
- **Cost per query**: Every search costs an LLM call. For high-QPS systems, this adds significant operational cost.

## Known Implementations
- **LlamaIndex** — `HyDEQueryTransform` with configurable LLM and prompt template; drop-in query transformation
- **LangChain** — `HypotheticalDocumentEmbedder` with multi-generation support
- **Custom** — simple to implement: LLM call → embed → search; ~20 lines of code
- **Vespa / Elasticsearch** — no native support; must be implemented at the application layer

## Trade-offs

### Pros
- **Significant recall improvement for vague queries** — 10-20% recall improvement reported on NL retrieval benchmarks for under-specified queries
- **Zero indexing overhead** — transformation happens at query time only; no re-indexing needed
- **Framework support** — LlamaIndex and LangChain have ready-made implementations
- **Complementary to document-side enrichment** — code-to-NL enriches documents, HyDE enriches queries; both can apply simultaneously

### Cons
- **Query-time LLM cost and latency** — 200-2000ms per query plus API cost; significant for interactive search
- **Inconsistent improvement** — helps vague semantic queries but can hurt precise keyword queries; must be selectively applied
- **Hallucination risk** — hypothetical document may lead retrieval astray if it doesn't match actual codebase patterns
- **Not useful for code-to-code queries** — when the user pastes code as the query, generating a hypothetical document adds nothing
- **Evaluation difficulty** — hard to know when HyDE helps vs. hurts without per-query evaluation
- **Complexity cost:** Low-Medium — the implementation is simple; the challenge is deciding when to apply it and handling latency

## Composability

| Technique | Compatible? | Notes |
|-----------|------------|-------|
| Hybrid BM25 + dense | Partially | HyDE improves dense side only; BM25 should use original query for exact matching |
| Code-to-NL translation | Yes, excellent | Code-to-NL enriches documents, HyDE enriches queries — complementary directions |
| Late chunking | Yes | HyDE affects query embedding; late chunking affects document embedding — independent |
| Reranking | Yes | HyDE improves recall of first-stage retrieval; reranker then refines precision |
| ColBERT | Partially | HyDE generates document-like text; ColBERT does token-level matching — less aligned |
| Contextual retrieval | Yes | Both enrich representations; contextual retrieval on documents, HyDE on queries |

## Verdict for Kenjutsu
- **Recommendation:** EVALUATE
- **Priority:** Layer 2 — benchmark after core pipeline is built; deploy selectively
- **Rationale:** HyDE is a compelling query-time optimization for Kenjutsu's NL-heavy query patterns (PR review questions, semantic code search), but its inconsistent benefit, query-time latency, and cost make it unsuitable as a default-on feature. The recommended approach: (1) build the core pipeline without HyDE, (2) benchmark HyDE on Kenjutsu's actual query distribution, (3) if beneficial, deploy it as a conditional enhancement — triggered for vague/semantic queries but bypassed for exact identifier lookups. A query classifier ("is this a keyword query or a semantic query?") would gate HyDE application. Note that code-to-NL translation at indexing time (document-side) addresses a similar gap with less query-time cost — evaluate both and compare.
