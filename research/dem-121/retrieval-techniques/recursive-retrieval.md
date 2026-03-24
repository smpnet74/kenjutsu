# Recursive Retrieval / Tree Index

## Overview
- **Category:** Retrieval strategy / index architecture
- **Key papers/implementations:** "RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval" — Sarthi et al. (ICLR 2024). LlamaIndex tree index and recursive retrieval architecture. "From Local to Global: A Graph RAG Approach" — Microsoft (2024, related concept for hierarchical summarization). Tree-of-summaries pattern in enterprise RAG systems.
- **Maturity:** Early production — RAPTOR published with strong results; LlamaIndex has tree index implementation; not yet standard in production RAG pipelines

## How It Works

Recursive retrieval organizes documents into a hierarchical tree structure where each level provides a different granularity of representation. The leaf nodes are the original chunks; intermediate nodes are summaries of their children; the root summarizes the entire corpus (or a large section of it). Retrieval traverses this tree from top to bottom, narrowing scope at each level.

**RAPTOR approach (bottom-up construction):**
```python
# Step 1: Start with leaf chunks
leaves = chunk_documents(corpus)
leaf_embeddings = [embed(chunk) for chunk in leaves]

# Step 2: Cluster similar chunks
clusters = cluster(leaf_embeddings, method="gaussian_mixture")

# Step 3: Summarize each cluster using an LLM
summaries_l1 = []
for cluster in clusters:
    cluster_texts = [leaves[i].text for i in cluster]
    summary = llm.summarize(cluster_texts)
    summaries_l1.append(summary)

# Step 4: Recursively cluster and summarize up the tree
summaries_l2 = cluster_and_summarize(summaries_l1)
summaries_l3 = cluster_and_summarize(summaries_l2)
# ... until a single root summary or manageable number of top-level nodes

# Step 5: All nodes (leaves + summaries at all levels) are embedded and searchable
all_nodes = leaves + summaries_l1 + summaries_l2 + summaries_l3
all_embeddings = [embed(node) for node in all_nodes]
```

**Retrieval strategies:**

**1. Flat search across all levels:** Embed query, search all nodes (leaves + summaries). Summaries match broad queries; leaves match specific queries. Simple and effective.

**2. Tree traversal (top-down):** Start at top-level summaries, find the most relevant subtree, descend to its children, repeat until reaching leaves. Efficient for large corpora — logarithmic search instead of linear.

**3. Collapsed tree (RAPTOR recommended):** Search across all layers simultaneously but return leaf nodes, using summary matches to boost their children's scores.

## Relevance to Code Retrieval
- **Applicable to Kenjutsu?** Partially — valuable for large codebase navigation; less critical for function-level retrieval
- **Which pipeline stage?** Indexing (tree construction) and retrieval (tree traversal)
- **Complementary or replacement?** Complementary — adds a hierarchical navigation layer on top of flat retrieval

### Code-Specific Strengths
- **Codebase-scale navigation**: For queries like "how does the payment system work?" — no single function answers this; a tree of summaries (payment module → payment service class → individual payment methods) can provide a coherent multi-level answer
- **Natural mapping to code structure**: Codebase already has a hierarchy: repository → package → module → class → function. The tree index can mirror this structure rather than using clustering.
- **Architecture-level queries**: PR reviewers asking "what subsystems does this change affect?" need architecture-level summaries that leaf-level retrieval cannot provide
- **Progressive disclosure**: Start with a high-level summary of what a module does, drill into specific classes, then individual functions — matches how developers explore unfamiliar code

### Code-Specific Limitations
- **Expensive tree construction**: Building the tree requires clustering + LLM summarization at each level. For a large codebase, this is significant compute (potentially more expensive than the entire initial embedding pipeline).
- **Staleness amplification**: When a leaf changes, all ancestor summaries potentially need regeneration. This cascading update problem is worse for trees than flat indices.
- **Diminishing returns with good flat retrieval**: If hybrid BM25 + dense retrieval with reranking already achieves good recall, the tree structure adds complexity without proportional quality improvement for most queries.
- **Code structure already provides hierarchy**: Unlike prose documents (where hierarchy must be inferred via clustering), code repositories have explicit structure (directories, modules, classes). A simpler approach — embedding at multiple granularities (function, class, file, module) without tree construction — may capture most of the benefit.

## Known Implementations
- **RAPTOR** — reference implementation available; clustering + recursive summarization pipeline
- **LlamaIndex** — `TreeIndex` with `TreeSelectLeafRetriever` and `TreeAllLeafRetriever`; `RecursiveRetriever` for hierarchical document structures
- **Custom** — building a code-specific tree using AST hierarchy (package → module → class → function) with LLM summaries at each level
- **Microsoft GraphRAG** — related approach using community detection on knowledge graphs instead of document clustering

## Trade-offs

### Pros
- **Multi-granularity retrieval** — handles both "what does this function do?" and "how does the payment system work?" queries
- **Efficient for very large corpora** — tree traversal is O(log n) vs. O(n) for flat search; valuable at codebase scale (millions of chunks)
- **Architecture-level understanding** — summary nodes capture cross-function and cross-file relationships that no single chunk can represent
- **RAPTOR showed strong results** — outperformed flat retrieval on QA benchmarks requiring multi-document reasoning

### Cons
- **High construction cost** — clustering + multi-level LLM summarization is expensive in both compute and API cost
- **Cascading staleness** — code changes propagate up the tree, requiring expensive summary regeneration
- **Complexity** — tree construction, maintenance, and traversal add significant system complexity
- **Overkill for most queries** — the majority of code search queries can be answered by a single function or file; tree traversal adds latency without benefit for these
- **Code has natural structure** — repositories already have directory/module hierarchy; building an additional tree may be redundant
- **Complexity cost:** High — tree construction, maintenance, multi-level embedding, and traversal logic; significant engineering investment

## Composability

| Technique | Compatible? | Notes |
|-----------|------------|-------|
| Hybrid BM25 + dense | Yes | BM25 on leaf text, dense retrieval across all tree levels |
| Reranking | Yes | Rerank candidates retrieved from any tree level |
| Parent-child retrieval | Overlapping | Parent-child is a 2-level tree; recursive retrieval generalizes to N levels |
| Code-to-NL translation | Yes | NL summaries at leaf level feed into tree construction |
| Contextual retrieval | Yes | Contextual enrichment at leaf level before tree construction |
| Late chunking | Yes | Apply to leaf-level embedding; tree summaries are separate |
| Knowledge graphs | Complementary | Trees capture hierarchical structure; graphs capture arbitrary relationships |

## Verdict for Kenjutsu
- **Recommendation:** DEFER
- **Priority:** Layer 3 / Future — investigate after core pipeline and code-specific needs are clearer
- **Rationale:** Recursive retrieval / tree indexing is intellectually compelling but operationally expensive for Kenjutsu's MVP. The construction cost (clustering + multi-level summarization), staleness management (cascading updates on code changes), and complexity are not justified when: (1) code already has natural hierarchy via AST/directory structure, (2) parent-child retrieval captures the most important 2-level case, and (3) hybrid search + reranking handles the majority of query types well. The specific case where tree indexing shines — architecture-level "how does X work?" queries — can be initially addressed by embedding module-level README/docstrings and file-level summaries without a full recursive tree. Revisit when Kenjutsu needs to support codebase-wide architectural queries at scale and simpler approaches have proven insufficient.
