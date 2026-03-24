# Parent-Child Retrieval

## Overview
- **Category:** Retrieval strategy / chunking hierarchy
- **Key papers/implementations:** Core concept in LlamaIndex's `AutoMergingRetriever` and `IndexNode` system. "Small-to-Big Retrieval" pattern documented across RAG literature. Elasticsearch nested documents. Production implementations in LlamaIndex, LangChain, and custom pipelines.
- **Maturity:** Production-proven — well-established pattern in RAG systems; LlamaIndex has mature implementations; widely deployed

## How It Works

Parent-child retrieval separates the retrieval unit from the context unit. You retrieve at a fine-grained level (child chunks) for precision, but return a larger context (parent chunk/document) for completeness. This solves the fundamental tension in chunking: small chunks are more precise for retrieval but lack context for understanding; large chunks provide context but dilute retrieval signals.

**Architecture:**
```
Document (file)
├── Parent chunk (class/module, ~1000-2000 tokens)
│   ├── Child chunk (function, ~200-500 tokens)
│   ├── Child chunk (function, ~200-500 tokens)
│   └── Child chunk (function, ~200-500 tokens)
└── Parent chunk (class/module, ~1000-2000 tokens)
    ├── Child chunk (function, ~200-500 tokens)
    └── Child chunk (function, ~200-500 tokens)
```

```python
# Indexing: embed at child (fine-grained) level
for parent in document.parent_chunks:
    for child in parent.child_chunks:
        child_embedding = embed(child.text)
        store(child.id, child_embedding, metadata={
            "parent_id": parent.id,
            "document_id": document.id
        })
    # Optionally store parent text for retrieval (not for embedding search)
    store_parent_text(parent.id, parent.text)

# Retrieval: search at child level, expand to parent
child_results = vector_search(query_embedding, child_index, top_k=20)

# Deduplicate by parent — if 3 children from the same parent match,
# that parent is highly relevant
parent_scores = {}
for child in child_results:
    pid = child.metadata["parent_id"]
    parent_scores[pid] = max(parent_scores.get(pid, 0), child.score)

# Return parent text (richer context) ranked by best child match
results = [get_parent_text(pid) for pid, _ in sorted(
    parent_scores.items(), key=lambda x: -x[1]
)]
```

**Auto-merging variant (LlamaIndex):** If more than a threshold (e.g., 60%) of a parent's children are retrieved, automatically merge up to the parent level — the system infers that the entire parent is relevant.

## Relevance to Code Retrieval
- **Applicable to Kenjutsu?** Yes — code has natural parent-child hierarchies (file→class→method, module→function)
- **Which pipeline stage?** Retrieval (post-retrieval expansion)
- **Complementary or replacement?** Complementary — enhances any retrieval approach with context expansion

### Code-Specific Strengths
- **Natural hierarchy for code**: Unlike prose (where parent-child boundaries are heuristic), code has deterministic hierarchies via AST: file → class → method → block. This makes parent-child retrieval especially clean for code.
- **Function-level precision, class-level context**: Retrieve the exact function that matches the query, but return the entire class — giving the LLM constructor, class fields, related methods, and docstrings.
- **Multi-function relevance signal**: If a query matches 3 functions within the same class, that's a strong signal the entire class is relevant — auto-merging captures this.
- **Diff-aware retrieval for PRs**: In code review, changes are at the line/function level but understanding requires file/module context. Parent-child naturally provides "changed function + surrounding context."

### Code-Specific Limitations
- **Hierarchy depth varies**: Python files may have flat function lists (1 level) while Java files have deeply nested inner classes (3+ levels). The hierarchy strategy must be language-aware.
- **Large parent chunks**: A 500-line class returned as "parent context" may exceed LLM context windows or dilute relevance. Parent size needs capping.
- **Cross-file parents don't exist naturally**: Functions that span files (via imports) don't have a single parent chunk. Parent-child is file-scoped.
- **Duplication in results**: If multiple children of the same parent are relevant, naive implementations return the parent multiple times.

## Known Implementations
- **LlamaIndex** — `AutoMergingRetriever` with configurable merge threshold; `IndexNode` for parent-child relationships; most mature implementation
- **LangChain** — `ParentDocumentRetriever` with configurable child/parent splitters
- **Elasticsearch** — nested documents with inner_hits for child-level search, parent-level return
- **Custom** — straightforward to implement: store parent_id metadata with each child chunk, group by parent after retrieval

## Trade-offs

### Pros
- **Best of both worlds** — fine-grained retrieval precision with rich context for understanding
- **Natural for code** — AST-defined hierarchies make chunk boundary selection deterministic
- **Improved LLM generation** — returning parent context gives the LLM more to work with, reducing hallucination
- **Relevance amplification** — multiple child matches from the same parent = strong relevance signal
- **No additional embedding cost** — only child chunks are embedded; parents are stored as text

### Cons
- **Larger returned context** — parent chunks are bigger, consuming more LLM context window and potentially including irrelevant code
- **Two-level storage** — must store both child embeddings and parent text; more complex data model
- **Merge threshold tuning** — auto-merging threshold affects precision/recall trade-off; requires experimentation
- **Language-specific hierarchy logic** — AST parsing for hierarchy extraction must be implemented per language
- **Complexity cost:** Low-Medium — LlamaIndex makes it easy; custom implementation requires parent-child relationship management

## Composability

| Technique | Compatible? | Notes |
|-----------|------------|-------|
| Hybrid BM25 + dense | Yes | Hybrid search at child level, parent expansion after |
| Reranking | Yes | Rerank child results, then expand to parents |
| Late chunking | Partially redundant | Late chunking gives child embeddings parent context; parent-child returns parent text. Can be complementary — better embeddings AND richer output |
| Contextual retrieval | Partially redundant | Both inject parent context into children; one at embedding time, one at retrieval time. Combining adds complexity |
| Code-to-NL translation | Yes | NL summaries on child chunks, parent expansion for context |
| HyDE | Yes | HyDE improves child retrieval; parent expansion provides context |
| Recursive retrieval | Extension | Recursive retrieval is a generalization of parent-child to arbitrary depth |

## Verdict for Kenjutsu
- **Recommendation:** ADOPT
- **Priority:** MVP — implement as part of the core chunking and retrieval strategy
- **Rationale:** Parent-child retrieval is a natural fit for code search and addresses one of Kenjutsu's core challenges: balancing retrieval precision (function-level) with context completeness (class/file-level). The AST-defined hierarchy for code makes this cleaner than for prose documents. For Kenjutsu's MVP: embed at function/method level, store class/file text as parent context, and return parent context with retrieval results. LlamaIndex's `AutoMergingRetriever` provides a solid starting implementation. This is foundational architecture — not an optimization to add later.
