# Multi-Vector Representations

## Overview
- **Category:** Embedding strategy
- **Key papers/implementations:** "Multi-Vector Retrieval as Sparse Alignment" — Chen et al. (2024). "Poly-encoders: Architectures and Pre-training Strategies for Fast and Accurate Multi-sentence Scoring" — Humeau et al. (ICLR 2020). "ME-BERT: Extractive and Abstractive Summarization for Multi-Document" and related multi-vector work. Related to but distinct from ColBERT's per-token multi-vector approach.
- **Maturity:** Early production — concept proven in research; practical implementations emerging in LlamaIndex and vector databases with multi-vector support (Qdrant, Milvus)

## How It Works

Multi-vector representations encode a single document as multiple embedding vectors, each capturing a different aspect or segment of the document. Unlike single-vector encoding (which compresses all semantics into one point in embedding space), multi-vector approaches distribute the document's meaning across several vectors, reducing the information bottleneck.

**Approaches:**

**1. Segment-based multi-vector:** Split a document into meaningful segments and embed each independently:
```python
# A code file produces multiple vectors
vectors = []
vectors.append(embed(file_docstring))        # intent/purpose
vectors.append(embed(function_signatures))    # API surface
vectors.append(embed(function_bodies))        # implementation details
vectors.append(embed(import_statements))      # dependency context
```

**2. Aspect-based multi-vector:** Use different embedding prompts or models to capture different facets:
```python
# Same document, different embedding perspectives
vectors = [
    embed(doc, instruction="Represent the functionality"),
    embed(doc, instruction="Represent the API signature"),
    embed(doc, instruction="Represent the error handling"),
]
```

**3. Learned multi-vector (Poly-encoders):** Train the model to produce a fixed number of attention-based "codes" that summarize different aspects of the input:
```python
# Model produces N context codes from attention
context_codes = poly_encoder.encode(document)  # [N, dim]
# At query time, attend over codes
score = attend(query_embedding, context_codes).max()
```

**Retrieval:** At query time, the query is compared against all vectors for a document. The final relevance score is typically the maximum similarity across all document vectors (MaxSim) or the sum of top-k similarities.

## Relevance to Code Retrieval
- **Applicable to Kenjutsu?** Yes — code documents are naturally multi-faceted (API surface, implementation logic, documentation, dependencies)
- **Which pipeline stage?** Indexing and retrieval
- **Complementary or replacement?** Can replace single-vector representation; complements other retrieval techniques

### Code-Specific Strengths
- **Natural decomposition for code**: Source files have well-defined aspects (imports, docstrings, signatures, bodies, tests) that map directly to multiple vectors. This is more natural for code than for prose.
- **Query-aspect alignment**: A query about "what this function does" matches against the docstring vector; a query about "functions that use pandas DataFrame" matches against the import/body vector. Single-vector must capture all of this in one point.
- **Reduced information loss for large files**: A 500-line file compressed to one 768-dim vector loses enormous detail. Five vectors capture 5x more information.
- **AST-driven segmentation**: Code's parseable structure makes segment boundary selection deterministic (function-level, class-level, block-level), unlike prose where segmentation is heuristic.

### Code-Specific Limitations
- **Storage multiplication**: N vectors per document means Nx storage, Nx indexing, and more complex retrieval logic
- **Segment quality variance**: Not all code segments embed equally well — a bare `import os` statement produces a weak embedding; a well-documented function produces a strong one
- **No standard approach**: Unlike late chunking or hybrid search, there's no single "right way" to decompose code into multiple vectors; requires experimentation
- **Cross-segment queries**: A query that spans multiple aspects ("function that reads a CSV file and handles encoding errors") needs to match across vectors, complicating the scoring function

## Known Implementations
- **LlamaIndex** — `MultiVectorRetriever` concept; `IndexNode` for parent-child multi-vector patterns
- **Qdrant** — named vectors and multi-vector support (v1.7+) enable storing and searching multiple vectors per point
- **Milvus** — multi-vector fields per entity
- **Custom / DIY** — most practical implementations are custom: embed segments separately, store with shared document ID, aggregate at retrieval time
- **ColBERT** — technically a multi-vector approach (per-token), but categorized separately due to distinct architecture

## Trade-offs

### Pros
- **Reduced information bottleneck** — captures more document semantics than a single vector, especially for long or multi-faceted documents
- **Natural for code** — code's structured nature makes aspect decomposition straightforward
- **Flexible precision** — more vectors = more precision; tunable per use case
- **Aspect-specific retrieval** — can search only signature vectors or only implementation vectors for different query types

### Cons
- **Linear storage increase** — N vectors per doc = Nx storage cost; at scale this is significant
- **Complex retrieval logic** — need to aggregate scores across vectors per document; most ANN indices return vectors, not documents, requiring a post-retrieval grouping step
- **No standard scoring function** — MaxSim, sum-of-top-k, and weighted-sum all have trade-offs; requires evaluation
- **Segment definition is art not science** — what constitutes a good "aspect" for code embedding is unclear; likely requires experimentation per language and query type
- **Complexity cost:** Medium — requires custom indexing/retrieval logic; no one-line framework integration

## Composability

| Technique | Compatible? | Notes |
|-----------|------------|-------|
| Hybrid BM25 + dense | Yes | Multi-vector on the dense side; BM25 operates on full text |
| Reranking | Yes | Multi-vector retrieval produces candidate documents; reranker scores full document |
| Late chunking | Orthogonal | Late chunking is about context-aware single vectors per chunk; multi-vector is about multiple vectors per document |
| Matryoshka / quantization | Yes | Each vector can be dimension-reduced and quantized independently |
| Parent-child retrieval | Overlapping | Both address "retrieve at fine granularity, return at document level"; may be redundant |
| HyDE | Yes | Generate hypothetical answer, compare against multi-vector document representation |
| ColBERT | Overlapping | ColBERT is a specific multi-vector approach (per-token); using both is redundant |

## Verdict for Kenjutsu
- **Recommendation:** EVALUATE
- **Priority:** Layer 3 — investigate after core pipeline is mature and retrieval quality needs are clear
- **Rationale:** Multi-vector representations are theoretically compelling for code (which has natural aspect decomposition), but the lack of standardized approaches, additional storage cost, and complex retrieval logic make this a research investment rather than an MVP feature. Kenjutsu should first exhaust simpler approaches (hybrid search, reranking, late chunking) and only pursue multi-vector if retrieval quality on long/complex code files remains unsatisfactory. The most practical near-term application is AST-driven segment embedding (embed functions independently within a file), which is partially addressed by smart chunking strategies and parent-child retrieval.
