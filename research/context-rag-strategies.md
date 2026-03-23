# Context and RAG Strategies for Code Review

- **Status:** review
- **Author:** Chief Architect
- **Date:** 2026-03-23
- **Issue:** DEM-108
- **Parent:** DEM-104

---

## Executive Summary

Full-codebase context is the primary differentiator in AI code review quality. Greptile's benchmark shows 82% bug detection with full indexing vs 44% for diff-only approaches. The recommended strategy for Kenjutsu is a hybrid pipeline: tree-sitter AST parsing for structure, function-level chunking with natural language descriptions, Voyage-code-3 embeddings, hybrid BM25+vector retrieval with cross-encoder reranking, and cheap heuristics (import graphs, co-change analysis) as a fast fallback. The key anti-pattern is "blind vector stuffing" — too many irrelevant chunks hurts worse than no context at all.

---

## 1. How Existing Tools Build Context

### CodeRabbit — Multi-Signal Hybrid Pipeline

CodeRabbit uses the most sophisticated context engineering of the three:

**AST-grep integration:** Uses ast-grep (Rust-based, built on tree-sitter) for deterministic pattern matching. YAML rules define security patterns (hardcoded credentials), network operations, database queries, resource management. Matched snippets become grounded context for the LLM, anchoring suggestions in verified structural information.

**LanceDB vector store:** Ingests code structure, issue tracker content (Jira, Linear), and historical reviews. Delivers sub-second (P99 < 1s) semantic search across 50,000+ daily PRs. Specific embedding models and chunking strategies are not publicly disclosed.

**Codegraph dependency analysis:** Two mechanisms: (1) a code graph of definitions and references; (2) co-change mining from commit history — if files A and B always change together, they're likely coupled even without direct imports. Enables cross-file reasoning.

**Multi-stage summarization:** Context gathering → codegraph mapping → semantic retrieval → standards application → tool signal integration (linters, security analyzers) → verification scripts (grep/ast-grep to confirm assumptions) → comment generation. Uses different model tiers: simpler models for summarization/triage, frontier models for deep reasoning.

**Context anti-patterns they've identified:**
- *Context confusion:* model latches on irrelevant detail
- *Context clash:* contradictory information causes hedging
- *Context poisoning:* hallucinated/mis-indexed snippets create fabricated references
- *Blind vector stuffing:* treating vector DBs as oracles instead of filters

### Greptile — Full-Repo AST Indexing

Greptile's core innovation: embed natural language descriptions of code, not code itself.

**Pipeline:**
1. Parse entire codebase into ASTs via tree-sitter
2. Recursively generate natural language docstrings for each AST node (leaf-up)
3. Embed the docstrings, not the source code
4. Store in vector DB (ChromaDB)

**Evidence:** Direct query-to-code semantic similarity: 0.7280. Query-to-natural-language-description: 0.8152 — a **12% improvement**. This is the key insight: translating code to natural language before embedding significantly improves retrieval.

**Graph-based context:** Constructs a complete graph with three node types: files, functions, external calls/variables. Edges map function calls, imports, variable access, cross-file dependencies. Enables multi-hop dependency tracing during review.

**Three-way retrieval:**
1. Semantic similarity search on embedded docstrings
2. Keyword search for exact matches
3. Agentic search — an AI agent reviews relevance and traces references through source code (built on Claude Agent SDK in v3)

**Feedback loop:** Developer upvote/downvote → embedding vectors stored per team. New comments blocked if high cosine similarity to 3+ downvoted comments. This improved addressed-comment rate from 19% to 55%+ within two weeks.

**Chunking insight:** Function-level isolation scores 0.768 similarity. Full file with correct function buried in noise: 0.739. Full file of unrelated code: 0.718. **Conclusion: chunk tightly at function level.**

### PR-Agent — Diff-Only with Heuristic Extension

The simplest approach, and the weakest for context:

**What it does:** Extends diff hunks to enclosing function/class boundaries. `extend_patch()` searches upward (default 8 lines) for an enclosing function/class definition. Pre-change context prioritized over post-change.

**What it misses:** Cross-file impact, duplicate code elsewhere, convention violations in non-modified files, architectural pattern mismatches. No codebase-wide semantic index, no code graph, no vector store.

**Token management:** Iteratively adds patches by language priority and token count until budget is reached. Remaining files listed by name only. Default budget: 32K tokens.

---

## 2. Embedding Approaches for Code

### Model Comparison (2025-2026)

| Model | Code Retrieval Quality | Dimensions | Context Window | Notes |
|---|---|---|---|---|
| **Voyage-code-3** | SOTA (+13.8% over OpenAI) | 2048/1024/512/256 | 32K tokens | Best for code; Matryoshka learning enables dimension flexibility |
| OpenAI text-embedding-3-large | Strong | 3072 | 8K tokens | General-purpose, good code performance |
| CodeSage-large-v2 | Good | Flexible (Matryoshka) | 1K tokens | Short context limits utility |
| Jina-v2-code | Unreliable benchmarks | — | — | CoSQA dataset has ~51% incorrect labels |
| Nomic Embed Code | 80-82% on retrieval tasks | — | — | — |

**Recommendation: Voyage-code-3 at 1024 dimensions.** Achieves 92.28% of full performance while outperforming OpenAI-v3-large at 3072 dims (78.48%) — better quality at 1/3 the storage. Binary quantization available for 32x storage reduction with minimal quality loss.

### Code-Specific Embedding Challenges

1. **Semantic gap:** Code and natural language occupy different embedding spaces. Greptile's 12% improvement validates translating code to natural language before embedding.
2. **Identifier significance:** Variable names, function signatures, type annotations carry semantic weight that generic embeddings may underweight.
3. **Cross-file relationships:** Isolated function embeddings lose import context, inheritance, and call patterns. Must include structural metadata.
4. **Benchmark contamination:** CoSQA has 51% incorrect labels; CodeSearchNet queries contain verbatim docstrings. Evaluate on real-world retrieval tasks, not academic benchmarks alone.

---

## 3. AST Parsing Strategies

### Tree-sitter as Standard

Tree-sitter is the de facto universal AST parser: production-proven (Neovim, Helix, Zed), supports virtually every language, provides incremental parsing for fast re-indexing.

### What to Extract

| Target | Purpose | Chunking Unit |
|---|---|---|
| Function signatures + bodies | Primary review context | Function-level chunk (recommended primary unit) |
| Class definitions + hierarchies | Inheritance and composition context | Class-level summary + per-method chunks |
| Import statements | Dependency graph construction | File-level metadata |
| Type annotations | Semantic constraints for typed languages | Included with function chunks |
| Call sites | Where changed functions are invoked | Cross-file reference graph |

### AST-grep for Pattern Matching

YAML rules define patterns over AST structures — language-agnostic through tree-sitter. Useful for security patterns (hardcoded credentials), API misuse, resource management violations. Provides deterministic findings that anchor LLM context in verified structural facts.

### Making AST Info Useful for LLMs

Two proven approaches:
1. **Greptile's approach:** Generate natural language summaries of each AST node recursively. Bridges the semantic gap. Higher quality retrieval but higher indexing cost (requires LLM call per node).
2. **CodeRabbit's approach:** Use AST-grep matches as grounded context snippets alongside the diff. Anchors LLM analysis in verified patterns. Deterministic, no LLM cost for extraction.

**Recommendation for Kenjutsu:** Combine both — AST-grep for deterministic pattern matching (security, conventions), natural language descriptions for semantic retrieval.

---

## 4. Chunking Strategies for Code

### Academic Evidence: cAST (EMNLP 2025)

Structural chunking via AST — the most rigorous evaluation available:
- Recursive split-then-merge: parse AST → fit large nodes into single chunks → recursively split oversized nodes → merge adjacent small siblings
- Uses non-whitespace character count (not lines) — equal line counts can carry wildly different code density
- Results: RepoEval recall +1.8-4.3 points, precision +1.2-3.3 points, Pass@1 +2.67-5.5 points, SWE-bench +2.7 points
- **Key finding:** Higher precision correlates with better generation more than recall. Top-k relevance matters more than comprehensive coverage.

### Practical Recommendations

**Primary unit: Function-level chunks via AST.**
- Isolate individual functions as chunks
- Include class definition header + imports with each method chunk for context
- Noise from surrounding unrelated code drops similarity by ~7%

**Hierarchical indexing (two-tier):**
- Summary index at file/module/directory level
- Detail index at function/class/block level
- Query searches summaries first → drills into details
- Adds 50-100ms latency, reduces irrelevant results ~40%

**Structural completeness:** No mid-function splitting. Each chunk is a complete syntactic unit.

**Monorepo handling:**
- Repo-level filtering before chunk-level queries
- Designate "golden repos" (best-practice exemplars)
- High-level content analysis to narrow to top 5-10 relevant repos
- Specialized chunking per file type: OpenAPI specs by endpoint, configs by section

---

## 5. RAG Pipeline Architecture for Code Review

### What to Retrieve for a PR Review

| Signal | Source | Cost |
|---|---|---|
| Directly affected code | Import graph / codegraph | Low (static analysis) |
| Co-change files | Git history mining | Low (git log) |
| Similar implementations | Semantic search on embeddings | Medium (vector query) |
| Type definitions | Import graph + AST | Low (static analysis) |
| Related test files | File-path heuristic (`*_test.go` ↔ `*.go`) | Low (pattern match) |
| Past PR decisions | Historical review embeddings | Medium (vector query) |
| Issue tracker context | Jira/Linear integration | Low (API call) |
| Team standards / conventions | Semantic search | Medium (vector query) |

### Retrieval Ranking

**Hybrid search is the consensus for code.** Formula: `H = (1-alpha) * K + alpha * V` where K = BM25 keyword score, V = vector similarity.

- Default weighting: 0.3 keyword / 0.7 vector
- Code may benefit from higher keyword weight due to importance of exact identifier matches
- Alternative: Reciprocal Rank Fusion (RRF) — `RRF_score(d) = sum(1/(k + rank))` where k=60. Combines rankings without score normalization.

**Reranking:** Retrieve 50-100 candidates, rerank to top 10 via cross-encoder (ms-marco-MiniLM, Cohere Rerank v3). Cross-encoders examine full query-document pairs simultaneously — deeper semantic understanding than bi-encoders.

### Token Budget Allocation

| Segment | Budget % | Notes |
|---|---|---|
| System prompt + cached codebase index | 60% | Prompt caching reduces costs up to 90% |
| Retrieved context chunks | 25% | Reranked top-k from hybrid search |
| Diff / conversation | 10% | The actual PR changes |
| Safety buffer | 5% | Output generation headroom |

### When RAG Helps vs When It Hurts

**RAG helps most when:**
- PR touches shared libraries, APIs, or cross-cutting concerns
- Review requires convention/pattern consistency checks
- The question is "does similar code exist elsewhere?"
- Historical review decisions inform current feedback

**RAG hurts when:**
- Too many irrelevant chunks dilute signal (noise problem)
- Outdated docstrings contradict current schema (context clash)
- Hallucinated/mis-indexed snippets create false references (context poisoning)
- Simple, self-contained changes that need no codebase context

**Mitigation strategies:**
1. Deduplication/differencing — collapse identical patterns
2. Summarization pipelines — compress context, trade fidelity for efficiency
3. Prioritization/truncation — token budgets per query, front-load summaries
4. Quarantining — related info in separate prompt threads (test failures in dedicated sub-threads)
5. Observability — token heatmaps to identify wasteful context

---

## 6. Accuracy vs Cost Trade-offs

### Embedding Costs for Large Codebases

**Indexing cost reduction strategies:**
- Embed natural language descriptions (Greptile/Qodo approach) — improves retrieval quality while adding an LLM call per chunk during indexing
- Voyage-code-3 Matryoshka learning — embed once at 2048 dims, truncate to 256 at query time (8x storage savings, minimal quality loss)
- Binary quantization — 32x storage reduction vs float32

### Incremental Indexing

**Cursor's Merkle tree approach:** Hierarchical hash tree of all files. Check root hashes every 10 minutes. Only re-upload/re-embed changed files. Cache embeddings keyed by chunk content hash — unchanged code reuses cached embeddings. Reduces embedding API costs 90%+ for typical daily changes.

**General principle:** Hash each chunk's content. On file change: re-chunk, compare hashes, only re-embed new/changed chunks. For PR review tools, re-index on PR creation against base branch — staleness tolerance is higher than for IDE tools.

### Prompt Caching

Claude and OpenAI support prompt caching — up to 90% cost reduction and 2x+ latency improvement for repeated large contexts. Greptile v3 achieved 75% lower inference costs despite 3x more context tokens through improved caching. **This is critical for Kenjutsu:** if the system prompt + codebase index summary is stable across reviews, prompt caching turns the 60% budget allocation into a near-free input.

### When to Use Expensive vs Cheap Context

| Approach | Cost | Quality | When to Use |
|---|---|---|---|
| Diff extension (heuristic) | Free | Low | Always (baseline) |
| Import graph traversal | Free | Medium | Always (static analysis) |
| Co-change analysis (git log) | Free | Medium | Always (git history mining) |
| File-path heuristic (test matching) | Free | Low-Medium | Always |
| Semantic search on embeddings | Medium | High | PRs touching shared code, APIs, cross-cutting concerns |
| Agentic multi-hop search | High | Highest | Complex PRs, architectural changes, unfamiliar codebases |
| Cross-encoder reranking | Medium | High improvement | Always when using semantic search |

**Inflection point:** For PRs touching 1-3 files in well-structured codebases, cheap heuristics (import graph + diff extension) may suffice. For PRs touching shared libraries, APIs, or cross-cutting concerns, full semantic retrieval with reranking is essential.

---

## 7. Benchmark Evidence

### Bug Detection Rates (DevToolsAcademy Macroscope 2025)

50 real-world PRs across 5 OSS repos:

| Tool | Bug Detection | Context Strategy |
|---|---|---|
| Greptile | 82% | Full codebase AST index + agentic search |
| CodeRabbit | 44-46% | AST-grep + LanceDB + codegraph |
| Cursor Bugbot | 42-58% | Unknown |
| Graphite Diamond | 6-18% | Unknown |

**Caveat:** Benchmark conducted by a third party using Greptile-adjacent methodology. Not peer-reviewed. Real-world effectiveness depends on codebase characteristics and what kinds of issues matter most.

**Takeaway:** Full-codebase indexing (Greptile) significantly outperforms partial-context approaches (CodeRabbit) and diff-only approaches (PR-Agent) on bug detection. The 82% vs 44% gap is substantial and consistent across methodologies.

---

## 8. Recommendations for Kenjutsu

### Context Pipeline Architecture

```
PR Event → Cheap Heuristics (always) → Semantic Retrieval (when needed)
                                           → Reranking → Token Budget
                                              → Multi-Stage LLM Review
```

**Layer 1 — Always (free):**
- Extend diff hunks to enclosing function/class (PR-Agent approach)
- Import graph traversal (tree-sitter + static analysis)
- Co-change analysis from git history
- Test file matching via path heuristics

**Layer 2 — When needed (medium cost):**
- Semantic search on function-level embeddings (Voyage-code-3, 1024 dims)
- Hybrid BM25 + vector retrieval
- Cross-encoder reranking to top 10

**Layer 3 — For complex PRs (higher cost):**
- Agentic multi-hop search (trace dependencies, check patterns)
- Historical review decision matching
- Issue tracker context integration

### Key Technical Decisions

1. **Embed natural language descriptions of code, not raw code.** The 12% retrieval improvement is too significant to ignore.
2. **Chunk at function level via tree-sitter AST.** Include class header + imports with each chunk.
3. **Use Voyage-code-3 at 1024 dimensions.** Best quality-to-storage ratio available.
4. **Implement hierarchical indexing** — summary tier for coarse filtering, detail tier for precise retrieval.
5. **Incremental indexing with content-hash caching.** Re-embed only changed chunks.
6. **Prompt caching is non-negotiable** for cost control at scale.
7. **Design for precision over recall.** Top-k relevance matters more than comprehensive coverage (cAST finding). Better to send 5 highly relevant chunks than 20 noisy ones.

---

## Sources

- [CodeRabbit — AI Native Universal Linter](https://www.coderabbit.ai/blog/ai-native-universal-linter-ast-grep-llm)
- [CodeRabbit — Massive Codebases](https://www.coderabbit.ai/blog/how-coderabbit-delivers-accurate-ai-code-reviews-on-massive-codebases)
- [CodeRabbit — Context Engineering](https://www.coderabbit.ai/blog/handling-ballooning-context-in-the-mcp-era-context-engineering-on-steroids)
- [LanceDB — CodeRabbit Case Study](https://lancedb.com/blog/case-study-coderabbit/)
- [Greptile — Semantic Codebase Search](https://www.greptile.com/blog/semantic-codebase-search)
- [Greptile — Graph-Based Context](https://www.greptile.com/docs/how-greptile-works/graph-based-codebase-context)
- [Greptile — v3 Agentic Review](https://www.greptile.com/blog/greptile-v3-agentic-code-review)
- [Greptile — v4](https://www.greptile.com/blog/greptile-v4)
- [Voyage-code-3 Blog](https://blog.voyageai.com/2024/12/04/voyage-code-3/)
- [cAST — EMNLP 2025](https://arxiv.org/html/2506.15655v1)
- [DevToolsAcademy — State of AI Code Review 2025](https://www.devtoolsacademy.com/blog/state-of-ai-code-review-tools-2025/)
- [Qodo — RAG for Large Scale Repos](https://www.qodo.ai/blog/rag-for-large-scale-code-repos/)
- [How Cursor Indexes Codebases](https://read.engineerscodex.com/p/how-cursor-indexes-codebases-fast)
- [ZenML — Greptile Feedback Loop](https://www.zenml.io/llmops-database/improving-ai-code-review-bot-comment-quality-through-vector-embeddings)
- [ICLR 2025 — Long-Context LLMs Meet RAG](https://proceedings.iclr.cc/paper_files/paper/2025/file/5df5b1f121c915d8bdd00db6aac20827-Paper-Conference.pdf)
