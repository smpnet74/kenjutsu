# Retrieval System Evaluation: LightRAG and Alternatives for Kenjutsu

- **Status:** review
- **Author:** Chief Architect
- **Date:** 2026-03-23
- **Issue:** DEM-114
- **Parent:** DEM-113

---

## Executive Summary

LightRAG is not the right retrieval system for Kenjutsu. While it is an impressive graph-enhanced RAG framework for natural language document retrieval (30K+ GitHub stars, EMNLP 2025 paper, 6,000x fewer tokens per query than Microsoft GraphRAG), its core design — LLM-based entity extraction to build knowledge graphs from prose — is fundamentally mismatched with code retrieval needs. Code requires deterministic AST-based structural analysis, not probabilistic entity extraction. Research on graph-RAG for codebases (Shereshevsky 2026, AST-derived DKB approach) confirms that AST-derived graphs significantly outperform LLM-extracted knowledge graphs for code retrieval tasks.

**Recommendation: Build a custom retrieval pipeline using LlamaIndex as the orchestration layer.** LlamaIndex provides the indexing primitives, vector store integrations, and query routing we need while allowing us to implement code-specific components (tree-sitter AST parsing, function-level chunking, Voyage-code-3 embeddings) that no prebuilt system offers out of the box. This aligns with the hybrid context pipeline architecture already proposed in the DEM-108 research.

---

## 1. LightRAG Deep Dive

### Overview

LightRAG (HKUDS, University of Hong Kong) is a graph-enhanced retrieval-augmented generation system published at EMNLP 2025. It combines knowledge graph construction with vector similarity search for dual-level retrieval across documents.

| Attribute | Detail |
|---|---|
| **License** | MIT |
| **GitHub stars** | 30.3K |
| **Language** | Python 3.10+ |
| **Paper** | EMNLP 2025 Findings |
| **Latest activity** | Active (6,747 commits, 172 contributors) |

### Architecture

**Indexing phase:**
1. Documents are chunked (default 1200 tokens, 100-token overlap)
2. An LLM extracts entities and relationships from each chunk
3. Entities become graph nodes; relationships become edges
4. Each node and edge stores a structured textual profile
5. Chunks are embedded and stored in a vector database

**Query phase — five retrieval modes:**
- **Naive:** Vector-only similarity search (baseline)
- **Local:** Graph traversal for direct entity connections
- **Global:** Cross-document relationship discovery via graph
- **Hybrid:** Combined local + global
- **Mixed:** Hybrid with cross-encoder reranking

**Storage backends (pluggable):**
- KV: JSON, PostgreSQL, Redis, MongoDB, OpenSearch
- Vector: NanoVectorDB, pgvector, Milvus, Chroma, Faiss, Qdrant, MongoDB
- Graph: NetworkX, Neo4j, PostgreSQL (AGE), OpenSearch

### Strengths

1. **Dramatically lower query cost than GraphRAG.** ~100 tokens per query vs. GraphRAG's ~610,000. This is a 6,000x reduction enabled by skipping community clustering and using lightweight dual-level retrieval.
2. **Incremental updates.** New documents are unioned into the existing graph without full rebuild (~50% faster update cycles vs. GraphRAG).
3. **Flexible storage backends.** Swappable KV, vector, and graph stores prevent vendor lock-in.
4. **Active community.** 30K+ stars, regular releases, Docker deployment, REST API server mode.
5. **Multiple query modes.** The naive→local→global→hybrid progression lets users trade off cost vs. depth.

### Weaknesses

1. **Designed for natural language, not code.** Entity extraction assumes prose — subjects, objects, relationships expressed in sentences. Code has a fundamentally different structure: functions, classes, imports, type annotations, call graphs. LightRAG's LLM-based extraction will miss structural relationships that AST parsing captures deterministically.
2. **Embedding model lock-in.** Switching embedding models requires deleting vector tables and re-indexing from scratch. No migration path.
3. **LLM dependency during indexing.** Entity extraction requires an LLM with 32K+ context and 32B+ parameters. This creates a significant indexing cost for large codebases (every chunk requires an LLM call).
4. **No AST awareness.** No tree-sitter integration, no language-aware chunking, no import graph extraction. The 1200-token fixed chunking will split functions mid-body.
5. **No code-specific retrieval signals.** No co-change analysis, no test-file matching, no type-hierarchy traversal — all signals identified as critical in DEM-108.
6. **Newer ecosystem.** Despite popularity, fewer production deployments reported than LlamaIndex or Haystack. REST API is recommended over direct library usage.

### Fit for Kenjutsu: Poor

Kenjutsu needs to retrieve contextually relevant code given a PR diff. The critical retrieval signals are:
- Function/class definitions affected by changes (AST-based)
- Import dependencies and call graphs (static analysis)
- Co-changed files (git history)
- Similar implementations elsewhere (semantic search on code embeddings)
- Related test files (path heuristics)

LightRAG addresses only the last category (semantic search), and even there, its chunking strategy is wrong for code. The knowledge graph it builds from LLM entity extraction would capture high-level concepts ("this file handles authentication") but miss the structural relationships ("function A calls function B which implements interface C") that make code review context useful.

**Adapting LightRAG for code would require replacing its core indexing pipeline** — at which point we're not using LightRAG, we're building a custom system that happens to share its storage layer.

---

## 2. Alternative Systems Evaluated

### 2.1 Microsoft GraphRAG

| Attribute | Detail |
|---|---|
| **License** | MIT |
| **GitHub stars** | 31.7K |
| **Latest version** | v3.0.6 (March 2026) |
| **Maintainer** | Microsoft Research (not officially supported product) |

**Architecture:** Five-stage pipeline — document chunking → LLM entity/relationship extraction → Leiden algorithm community clustering → community summary report generation → dual-mode querying (local entity search + global community-based synthesis).

**Key differentiator:** Community detection and hierarchical summarization enable "global queries" that address themes across entire datasets ("what are the main security concerns in this codebase?"). No other system does this well.

**Cost:** Indexing is expensive — original benchmarks showed $33K for large datasets. LazyGraphRAG (2025) reduces indexing cost to 0.1% of full GraphRAG by deferring graph construction to query time, but this is a separate system with different trade-offs.

**Strengths:**
- Strongest global/thematic query capability
- Hierarchical summaries provide multi-resolution context
- MIT licensed, large community

**Weaknesses:**
- Extremely expensive indexing (LLM calls per chunk × community clustering)
- Full rebuild required on document updates (no incremental)
- Same NLP-oriented entity extraction problem as LightRAG
- Complex infrastructure requirements
- "Not officially supported" Microsoft warning

**Fit for Kenjutsu: Poor.** Same fundamental mismatch as LightRAG (LLM entity extraction for code), compounded by prohibitive indexing costs and no incremental update support. The global query capability is interesting for "what are the main patterns in this codebase?" questions but not essential for PR review context.

### 2.2 R2R (RAG to Riches, SciPhi-AI)

| Attribute | Detail |
|---|---|
| **License** | MIT |
| **GitHub stars** | 7.7K |
| **Latest version** | v3.6.5 (June 2025) |
| **Maintainer** | SciPhi-AI |

**Architecture:** REST API-first system with three core pipelines — Ingestion (document parsing → embeddings), Embedding (vector storage), RAG (retrieval + LLM generation). Includes automatic knowledge graph extraction, hybrid search (semantic + keyword with RRF), and a Deep Research API for multi-step agentic reasoning.

**Strengths:**
- Production-oriented from day one (REST API, auth, observability)
- Hybrid search with reciprocal rank fusion built-in
- Knowledge graph extraction + vector search combined
- Python and JavaScript SDKs
- Docker deployment with PostgreSQL backend

**Weaknesses:**
- Smaller community (7.7K stars, 70 contributors)
- No code-specific features (same general-purpose RAG approach)
- Less flexible than LlamaIndex for custom indexing strategies
- Opinionated architecture — harder to swap components
- Fewer storage backend options

**Fit for Kenjutsu: Moderate.** R2R's hybrid search and production infrastructure are relevant, but it's a complete system rather than a composable toolkit. Integrating custom AST-based indexing would mean working against R2R's opinions rather than with them. Better suited as a standalone knowledge base than as an embedded retrieval component.

### 2.3 Cognee

| Attribute | Detail |
|---|---|
| **License** | Apache-2.0 |
| **GitHub stars** | 14.5K |
| **Latest version** | v0.5.5 (March 2026) |
| **Maintainer** | Topoteretes |

**Architecture:** Memory-first knowledge engine combining vector search, graph databases, and cognitive science approaches. Modular pipeline: ingestion (30+ data sources) → enrichment (embeddings + graph "memify") → retrieval (graph traversal + vector similarity + time filtering). Key abstraction: progressive learning — the system accumulates knowledge incrementally without full reprocessing.

**Strengths:**
- Memory-first design ideal for agentic systems
- Graph + vector hybrid unified architecture
- Multi-backend support (NetworkX for dev, Neo4j/FalkorDB for prod)
- Tenant isolation and OTEL observability
- Apache-2.0 license
- Progressive/incremental learning

**Weaknesses:**
- Pre-v1.0 (v0.5.5) — API stability not guaranteed
- Incomplete documentation and TypeScript support
- Scaling concerns at terabyte-level datasets
- Smaller contributor base relative to maturity expectations
- No code-specific indexing or retrieval features

**Fit for Kenjutsu: Moderate.** Cognee's progressive learning and agentic memory model are conceptually interesting for a code review tool that should learn from feedback over time. However, it's immature (pre-v1.0) and, like all systems evaluated, lacks code-specific features. Using Cognee would mean building all code indexing on top of a foundation that may change significantly before v1.0.

### 2.4 LlamaIndex

| Attribute | Detail |
|---|---|
| **License** | MIT |
| **GitHub stars** | 47.9K |
| **Latest version** | v0.14.18 (March 2026) |
| **Maintainer** | LlamaIndex Inc. (formerly GPT Index) |

**Architecture:** Data framework connecting LLMs with private data through modular components. Core abstractions: Documents → Nodes → Index (vector, keyword, knowledge graph, or custom) → QueryEngine → Response. 300+ integration packages covering LLM providers, vector stores, data connectors, and evaluation tools. LlamaCloud available as managed SaaS for ingestion/retrieval.

**Strengths:**
- Largest ecosystem (47.9K stars, 300+ integrations)
- Highly composable — custom node parsers, index types, and retrievers
- Supports knowledge graph indexing alongside vector and keyword
- Custom chunking strategies via NodeParser interface
- Multiple retrieval strategies: vector, keyword, hybrid, recursive, auto-routing
- Extensive documentation and community
- MIT licensed

**Weaknesses:**
- General-purpose framework — no code-specific components out of the box
- Complexity can be high for simple use cases (deep abstraction layers)
- Version churn — API changes between minor versions have been disruptive
- Performance overhead from abstraction layers vs. direct vector DB access

**Fit for Kenjutsu: Good.** LlamaIndex is the strongest candidate for the orchestration layer of Kenjutsu's retrieval pipeline. Its NodeParser interface allows implementing custom AST-based chunking via tree-sitter. Custom retrievers can compose the multi-signal approach (import graph + co-change + semantic search) defined in DEM-108. The 300+ integrations mean we can swap embedding models (Voyage-code-3), vector stores (Qdrant, pgvector), and LLM providers without rewriting retrieval logic. The trade-off is abstraction overhead — but for a system that needs to compose multiple retrieval strategies, the abstraction pays for itself.

### 2.5 Haystack (deepset)

| Attribute | Detail |
|---|---|
| **License** | Apache-2.0 |
| **GitHub stars** | ~24.6K |
| **Latest version** | v2.26 (March 2026) |
| **Maintainer** | deepset GmbH |

**Architecture:** Component-based pipeline orchestration framework. Every component implements a standard interface (input/output types). Components are composed into directed acyclic graph pipelines. Built-in components for document processing, retrieval, generation, and evaluation. Technology-agnostic — components can wrap any library or API.

**Strengths:**
- Production-grade pipeline orchestration (used by enterprises)
- Technology-agnostic component model — easy to create custom components
- Strong evaluation framework (RAGAS integration)
- Visual pipeline builder
- Low token usage (~1.57K per query in benchmarks) and fast (~5.9ms)
- Apache-2.0 license

**Weaknesses:**
- Higher-level orchestration framework — less RAG-specific than LlamaIndex
- Steeper learning curve for the component/pipeline model
- Fewer pre-built integrations than LlamaIndex (though still extensive)
- deepset's commercial focus (deepset Cloud) may influence OSS roadmap

**Fit for Kenjutsu: Good.** Haystack's component model is well-suited for Kenjutsu's multi-signal retrieval pipeline. Each retrieval signal (AST analysis, git co-change, semantic search, reranking) would be a component, composed into a pipeline. The evaluation framework is a plus for tuning retrieval quality. However, LlamaIndex offers more pre-built retrieval-specific components and a larger ecosystem for the RAG use case specifically.

---

## 3. Comparative Matrix

| Dimension | LightRAG | GraphRAG | R2R | Cognee | LlamaIndex | Haystack | Build from Scratch |
|---|---|---|---|---|---|---|---|
| **License** | MIT | MIT | MIT | Apache-2.0 | MIT | Apache-2.0 | N/A |
| **GitHub stars** | 30.3K | 31.7K | 7.7K | 14.5K | 47.9K | 24.6K | N/A |
| **Maturity** | Medium (EMNLP 2025) | Medium (MS Research) | Medium | Low (pre-v1.0) | High | High | Depends on team |
| **Code-specific features** | None | None | None | None | None (extensible) | None (extensible) | Full control |
| **AST/tree-sitter support** | No | No | No | No | Via custom NodeParser | Via custom component | Native |
| **Graph capabilities** | Core feature | Core feature | Built-in extraction | Core feature | Supported index type | Via custom component | Build as needed |
| **Incremental updates** | Yes (graph union) | No (full rebuild) | Yes | Yes (progressive) | Yes | Yes | Build as needed |
| **Hybrid search (BM25+vector)** | Yes (mixed mode) | No | Yes (RRF) | Yes | Yes | Yes | Build as needed |
| **Storage flexibility** | Excellent (12+ backends) | Limited | PostgreSQL-centric | Good (multi-backend) | Excellent (50+ stores) | Good | Full control |
| **Embedding flexibility** | Limited (model lock-in) | Flexible | Flexible | Flexible | Excellent | Excellent | Full control |
| **Query cost** | Very low (~100 tokens) | Very high (~610K tokens) | Low-medium | Low-medium | Depends on pipeline | Depends on pipeline | Depends on design |
| **Indexing cost** | High (LLM per chunk) | Very high (LLM + clustering) | Medium | Medium | Low (no LLM required) | Low (no LLM required) | Low (AST = free) |
| **Integration effort** | Medium (API/SDK) | High (complex infra) | Medium (REST API) | Medium (SDK) | Low (pip + compose) | Low (pip + compose) | High (build everything) |
| **Maintenance burden** | Low (managed updates) | Medium (complex system) | Low | Medium (pre-v1.0 churn) | Low (stable ecosystem) | Low (stable ecosystem) | High (own everything) |
| **Fit for code review** | Poor | Poor | Moderate | Moderate | Good | Good | Excellent |

---

## 4. Critical Finding: LLM Entity Extraction vs. AST Parsing for Code

The most important technical finding in this evaluation is that **all graph-based RAG systems (LightRAG, GraphRAG, R2R, Cognee) use LLM-based entity extraction**, which is designed for natural language documents. Recent research (Shereshevsky 2026, AST-derived DKB) demonstrates that for code retrieval:

1. **AST-derived graphs outperform LLM-extracted graphs** on code retrieval benchmarks (SWE-bench, RepoEval). Deterministic structural analysis captures function dependencies, call graphs, and type hierarchies that LLM extraction misses or hallucinates.

2. **AST parsing is free; LLM extraction is expensive.** Tree-sitter parses a file in milliseconds with zero API cost. LLM entity extraction costs tokens per chunk and takes seconds per call. For a codebase with thousands of files, the cost difference is orders of magnitude.

3. **Structural accuracy matters more than semantic richness for code.** When reviewing a PR, knowing that "function A calls function B which implements interface C" (AST-derived) is more useful than knowing "this module handles authentication" (LLM-extracted).

4. **Hybrid approaches win.** The DEM-108 research already identified this: AST-grep for deterministic structure + natural language descriptions for semantic retrieval. The best code retrieval system combines cheap structural analysis (always) with selective semantic enrichment (when needed).

This finding is the primary reason none of the evaluated prebuilt systems are suitable as Kenjutsu's complete retrieval solution. They solve the wrong problem — document retrieval — while Kenjutsu needs code retrieval.

---

## 5. Recommendation

### Primary: Build custom retrieval with LlamaIndex as orchestration layer

**What this means:**
- Use LlamaIndex's framework for index management, query routing, and retrieval composition
- Implement custom components for code-specific needs:
  - **Tree-sitter NodeParser** — AST-based function-level chunking (replacing LlamaIndex's default text splitter)
  - **Import graph retriever** — static analysis via tree-sitter for dependency resolution
  - **Co-change retriever** — git log mining for historically coupled files
  - **Test file matcher** — path heuristic component
- Use LlamaIndex's built-in hybrid search (BM25 + vector) with Voyage-code-3 embeddings
- Use LlamaIndex's cross-encoder reranking integration
- Store embeddings in Qdrant or pgvector via LlamaIndex's vector store integrations

**Why LlamaIndex over Haystack:**
- Larger ecosystem with more RAG-specific pre-built components
- NodeParser interface is a natural extension point for AST-based chunking
- More vector store and embedding model integrations
- Both are MIT/Apache-2.0 — licensing is not a differentiator

**Why not build entirely from scratch:**
- LlamaIndex handles vector store abstraction, query routing, hybrid search composition, and incremental indexing — rebuilding these provides no competitive advantage
- The 300+ integrations mean we can swap Voyage-code-3 for a better model when one appears, or switch from Qdrant to pgvector, without rewriting retrieval logic
- Custom components are where our differentiation lives (AST parsing, code-specific signals) — LlamaIndex lets us focus effort there

**Why not LightRAG or other graph-RAG systems:**
- Code retrieval needs AST-derived structure, not LLM-extracted entities
- Adopting LightRAG and replacing its core indexing pipeline means we're building custom anyway, but with an additional dependency and its constraints (embedding model lock-in, async initialization requirements)
- The query cost advantage of LightRAG (100 tokens vs. GraphRAG's 610K) is irrelevant when we're not using LLM-based entity extraction at all — our AST-based retrieval has zero LLM cost at query time

### Architecture Alignment

This recommendation aligns directly with the DEM-108 context pipeline architecture:

```
PR Event → Layer 1 (free heuristics) → Layer 2 (semantic retrieval) → Layer 3 (agentic search)
```

**Layer 1 — Custom components (always, free):**
- Tree-sitter AST parsing → import graph traversal (custom LlamaIndex retriever)
- Git co-change analysis (custom retriever)
- Test file matching (custom retriever)
- Diff extension to enclosing function/class (custom NodeParser)

**Layer 2 — LlamaIndex built-ins (when needed, medium cost):**
- Function-level embeddings via Voyage-code-3 (LlamaIndex embedding integration)
- Hybrid BM25 + vector retrieval (LlamaIndex's hybrid search)
- Cross-encoder reranking (LlamaIndex's reranking integration)

**Layer 3 — Future (higher cost):**
- Agentic multi-hop search (LlamaIndex agent framework)
- Historical review matching (custom retriever)

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LlamaIndex API churn between versions | Medium | Medium | Pin major version, abstract behind internal interfaces |
| Custom component maintenance burden | Medium | Medium | Keep components small and well-tested; AST parsing is deterministic |
| Voyage-code-3 availability/pricing changes | Low | Medium | LlamaIndex's embedding abstraction enables model swap |
| LlamaIndex ecosystem shifts toward LlamaCloud | Low | Low | MIT license ensures OSS remains available |

### What to Watch

1. **Cognee v1.0** — If Cognee stabilizes and adds code-specific features, its memory-first architecture could be valuable for Kenjutsu's feedback learning loop (post-MVP).
2. **LightRAG code extensions** — If the community builds AST-based entity extractors for LightRAG, it could become viable. Monitor the GitHub issues/PRs.
3. **Code-specific RAG papers** — The AST-derived graph-RAG research (2026) is early. Production-ready code retrieval frameworks may emerge.

---

## 6. Decision Summary

| Question | Answer |
|---|---|
| **Is LightRAG viable for Kenjutsu?** | No. Its LLM-based entity extraction is designed for natural language documents, not code. |
| **Are other prebuilt systems viable?** | Not as complete solutions. None have code-specific retrieval features. |
| **Best available option?** | LlamaIndex as orchestration layer + custom code-specific components. |
| **Why not build entirely from scratch?** | LlamaIndex handles vector store abstraction, hybrid search, and query routing — no value in rebuilding those. Focus custom work on code-specific differentiation. |
| **Primary risk?** | LlamaIndex API churn. Mitigate with internal abstraction layer. |
| **Alignment with prior research?** | Direct alignment with DEM-108 hybrid context pipeline architecture. |

---

## Sources

- [LightRAG — GitHub (HKUDS)](https://github.com/HKUDS/LightRAG)
- [LightRAG — EMNLP 2025 Paper](https://aclanthology.org/2025.findings-emnlp.568.pdf)
- [Microsoft GraphRAG — GitHub](https://github.com/microsoft/graphrag)
- [LazyGraphRAG — Microsoft Research](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/)
- [R2R — GitHub (SciPhi-AI)](https://github.com/SciPhi-AI/R2R)
- [Cognee — GitHub (Topoteretes)](https://github.com/topoteretes/cognee)
- [LlamaIndex — GitHub](https://github.com/run-llama/llama_index)
- [Haystack — GitHub (deepset)](https://github.com/deepset-ai/haystack)
- [GraphRAG vs LightRAG Comparison](https://lilys.ai/en/notes/get-your-first-users-20260207/graphrag-lightrag-comparison)
- [GraphRAG vs LightRAG — Maarga Systems](https://www.maargasystems.com/2025/05/12/understanding-graphrag-vs-lightrag-a-comparative-analysis-for-enhanced-knowledge-retrieval/)
- [Reliable Graph-RAG for Codebases: AST-Derived (2026)](https://arxiv.org/pdf/2601.08773)
- [15 Best Open-Source RAG Frameworks (2026) — Firecrawl](https://www.firecrawl.dev/blog/best-open-source-rag-frameworks)
- [RAG Frameworks Comparison — Pathway](https://pathway.com/rag-frameworks)
- [Cognee — From RAG to Graphs (Memgraph)](https://memgraph.com/blog/from-rag-to-graphs-cognee-ai-memory)
- [cAST — Structural Chunking via AST (EMNLP 2025)](https://arxiv.org/html/2506.15655v1)
