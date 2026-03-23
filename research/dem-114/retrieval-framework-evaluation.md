# Retrieval Framework Evaluation for Kenjutsu

- **Status:** draft
- **Author:** Chief Architect
- **Date:** 2026-03-23
- **Issue:** DEM-114
- **Parent:** DEM-113

---

## Executive Summary

Kenjutsu needs a retrieval pipeline that can surface contextually relevant code given a PR diff. This requires code-specific capabilities — AST parsing, import graph traversal, co-change analysis, function-level chunking — that no prebuilt system offers out of the box. The question is not "which system solves code retrieval for us?" but "which orchestration framework is the best foundation for building our custom code retrieval pipeline?"

This evaluation first explains why graph-RAG systems (LightRAG, GraphRAG, etc.) are a category mismatch for code retrieval, then conducts an apples-to-apples comparison of six RAG/AI orchestration frameworks that could serve as the foundation layer: **LlamaIndex**, **Haystack**, **LangChain**, **Semantic Kernel**, **DSPy**, and **txtai**.

**Recommendation:** LlamaIndex as the orchestration layer, with LangGraph available as a complementary agent framework if needed. LlamaIndex provides the deepest retrieval-specific primitives (hierarchical indexing, hybrid search, custom node parsers, reranking) with the largest integration ecosystem, minimizing the custom code needed to compose Kenjutsu's multi-signal retrieval pipeline.

---

## 1. What Kenjutsu Needs from a Retrieval Framework

Before evaluating frameworks, we need to define what Kenjutsu actually requires. The DEM-104 research established the context pipeline architecture — three layers of retrieval signals, from cheap heuristics to semantic search to agentic reasoning. This section summarizes those requirements independently so the framework evaluation stands on its own.

### 1.1 The Retrieval Problem

When a PR is opened, Kenjutsu must retrieve the code context most relevant to reviewing the changes. This includes:

- **Directly affected code:** Functions/classes that the changed code calls, imports, or implements
- **Co-changed files:** Files that historically change together with the modified files
- **Similar implementations:** Code elsewhere in the repo that follows similar patterns
- **Related tests:** Test files corresponding to changed source files
- **Type definitions and interfaces:** Contracts that constrain the changed code

### 1.2 Required Framework Capabilities

| Capability | Why Kenjutsu Needs It |
|---|---|
| **Custom component extensibility** | We must plug in tree-sitter AST parsing, git co-change analysis, and import graph traversal — none of which exist in any framework |
| **Multiple retrieval strategies** | Combine keyword (BM25), vector similarity, and custom retrievers into a single pipeline |
| **Custom chunking** | Code must be chunked at function/class boundaries via AST, not by token count or character splits |
| **Embedding model flexibility** | Must support Voyage-code-3 (or future code-specific models) without lock-in |
| **Vector store abstraction** | Swap between pgvector, Qdrant, or other stores without rewriting retrieval logic |
| **Reranking support** | Cross-encoder reranking of retrieved candidates to maximize precision |
| **Incremental indexing** | Re-index only changed files on each PR, not the entire codebase |
| **Query routing** | Route simple PRs through cheap heuristics, complex PRs through full semantic retrieval |
| **Python ecosystem** | Kenjutsu's stack is Python (FastAPI, tree-sitter, PyGithub) |
| **Evaluation tools** | Measure and tune retrieval quality over time |

---

## 2. Why Graph-RAG Systems Are the Wrong Category

The original version of this research compared LlamaIndex against graph-RAG systems (GraphRAG, R2R, Cognee, LightRAG). That was an apples-to-oranges comparison. Here is a brief explanation of why graph-RAG is a category mismatch, preserving the LightRAG assessment from the first version.

### 2.1 LightRAG Assessment

LightRAG (HKUDS, University of Hong Kong, MIT license, 30.3K GitHub stars) is a graph-enhanced RAG system that builds knowledge graphs from documents via LLM-based entity extraction. It is well-designed for its intended use case — natural language document retrieval with relationship-aware queries.

**Why it does not fit Kenjutsu:**

1. **Entity extraction assumes prose.** LightRAG's LLM extracts subjects, objects, and relationships from sentences. Code has a fundamentally different structure: functions, classes, imports, type hierarchies. LLM extraction will miss structural relationships that AST parsing captures deterministically.
2. **Fixed-token chunking splits code at wrong boundaries.** LightRAG's default 1200-token chunking will split functions mid-body. Code must be chunked at syntactic boundaries (function, class, module).
3. **No code-specific retrieval signals.** No co-change analysis, no test-file matching, no type-hierarchy traversal, no import graph extraction.
4. **Embedding model lock-in.** Switching embedding models requires deleting vector tables and full re-index.
5. **Adapting LightRAG for code means replacing its core.** At that point, you are building a custom system that happens to share LightRAG's storage layer — an unnecessary dependency.

**The same fundamental mismatch applies to all graph-RAG systems** (Microsoft GraphRAG, R2R, Cognee) that rely on LLM-based entity extraction. The knowledge graphs they build capture high-level concepts ("this module handles authentication") but miss the structural relationships ("function A calls function B which implements interface C") that make code review context useful.

**Bottom line:** Graph-RAG systems solve document retrieval. Kenjutsu needs code retrieval. These are different problems requiring different tools.

### 2.2 What Code Retrieval Actually Needs

For code, the graph that matters is derived from **AST parsing** (tree-sitter), not LLM entity extraction:

| Signal | Source | Cost |
|---|---|---|
| Function/class dependencies | tree-sitter AST + import resolution | Free (static analysis) |
| Call graphs | tree-sitter cross-reference | Free (static analysis) |
| Co-changed files | git log mining | Free (git history) |
| Type hierarchies | tree-sitter + language-specific queries | Free (static analysis) |
| Similar implementations | Embedding similarity search | Medium (vector query) |
| Pattern violations | AST-grep pattern matching | Free (deterministic) |

AST-derived structure is deterministic, free, and structurally accurate. LLM-extracted entities are probabilistic, expensive, and optimized for prose. For code retrieval, AST wins on every axis.

---

## 3. Framework Evaluation

The following six frameworks are evaluated as potential orchestration layers for Kenjutsu's custom retrieval pipeline. All are open-source, Python-compatible, and actively maintained.

### 3.1 LlamaIndex

| Attribute | Detail |
|---|---|
| **License** | MIT |
| **GitHub stars** | 47,912 |
| **Forks** | 7,082 |
| **Primary language** | Python |
| **Latest version** | v0.14.x (March 2026) |
| **Maintainer** | LlamaIndex Inc. |

**What it is:** A data framework purpose-built for connecting LLMs with private data through RAG. Retrieval is the core design problem — everything else is secondary.

**Architecture:** Documents → Nodes → Index (vector, keyword, knowledge graph, or custom) → QueryEngine → Response. 300+ integration packages for LLM providers, vector stores, data connectors, and evaluation tools.

**Strengths for Kenjutsu:**

1. **Deepest retrieval primitives.** Hierarchical indexing (summary + detail tiers), hybrid search (BM25 + vector), recursive retrieval, auto-merging retriever, sub-question decomposition, and query routing are all built-in and composable.
2. **NodeParser interface.** The natural extension point for custom chunking. Implementing a tree-sitter-based NodeParser that chunks code at function/class boundaries is a well-documented pattern. We write one class; LlamaIndex handles the rest of the indexing pipeline.
3. **Custom retrievers.** The BaseRetriever interface lets us implement import graph traversal, co-change analysis, and test-file matching as first-class retrieval components that compose with LlamaIndex's built-in retrievers.
4. **Largest integration ecosystem.** 300+ integrations including Voyage-code-3 embeddings, Qdrant, pgvector, Cohere Rerank, and every major LLM provider. Switching any component is a configuration change, not a rewrite.
5. **Hybrid search built-in.** BM25 + vector retrieval with configurable weighting — exactly what the DEM-104 research recommended.
6. **Evaluation tools.** Built-in support for RAGAS-style evaluation metrics to measure retrieval quality.

**Weaknesses:**

1. **Abstraction overhead.** Deep abstraction layers add performance overhead vs. direct vector DB access. For a code review tool processing one PR at a time, this is acceptable.
2. **API churn.** Breaking changes between minor versions have historically been disruptive. Mitigate by pinning major version and abstracting behind internal interfaces.
3. **Complexity for simple use cases.** The abstraction depth is overkill for a simple vector search. But Kenjutsu's multi-signal pipeline is not a simple use case.
4. **General-purpose.** No code-specific components out of the box — but the extension points are precisely where we need them.

**Fit for Kenjutsu: Strong.** LlamaIndex treats RAG as the core problem, which is exactly Kenjutsu's core problem. The NodeParser and BaseRetriever interfaces are natural extension points for our code-specific components. The 300+ integrations mean we can swap embedding models, vector stores, and LLM providers without rewriting retrieval logic.

### 3.2 Haystack (deepset)

| Attribute | Detail |
|---|---|
| **License** | Apache-2.0 |
| **GitHub stars** | 24,593 |
| **Forks** | 2,672 |
| **Primary language** | Python |
| **Latest version** | v2.26 (March 2026) |
| **Maintainer** | deepset GmbH |

**What it is:** An AI orchestration framework for building production-ready LLM applications with explicit control over retrieval, routing, memory, and generation.

**Architecture:** Component-based directed acyclic graph (DAG) pipelines. Every component implements a standard input/output interface. Components are composed into pipelines that can branch, loop, and route.

**Strengths for Kenjutsu:**

1. **Technology-agnostic component model.** Each retrieval signal (AST analysis, git co-change, semantic search, reranking) would be a custom component with a standard interface. Clean separation of concerns.
2. **Production-grade infrastructure.** Serializable pipelines, cloud-agnostic deployment, logging, monitoring, and Kubernetes-ready. Enterprise-proven.
3. **Strong evaluation framework.** RAGAS integration for measuring retrieval quality — important for tuning Kenjutsu's precision over time.
4. **DAG pipeline model.** Natural fit for Kenjutsu's multi-signal approach: fan-out to multiple retrievers, merge results, rerank.
5. **Low token usage.** Benchmarks show ~1.57K tokens per query and ~5.9ms latency — efficient by design.
6. **Apache-2.0 license.** No commercial restrictions.

**Weaknesses:**

1. **Higher-level orchestration focus.** Haystack is a general AI orchestration framework, not a RAG-specific toolkit. Less pre-built retrieval infrastructure than LlamaIndex.
2. **Steeper learning curve.** The component/pipeline model requires understanding Haystack's execution semantics, input/output contracts, and pipeline construction patterns.
3. **Fewer pre-built retrieval components.** No built-in hierarchical indexing, auto-merging retriever, or sub-question decomposition. These would need to be built as custom components.
4. **Smaller ecosystem.** Fewer integrations than LlamaIndex, though still extensive. Fewer community examples for RAG-specific patterns.
5. **Commercial influence.** deepset Cloud (managed platform) may influence OSS roadmap priorities.

**Fit for Kenjutsu: Good.** Haystack's component model is architecturally clean and well-suited for composing multiple retrieval signals. However, LlamaIndex provides more retrieval-specific primitives out of the box, meaning less custom code to write. Haystack would be the stronger choice if Kenjutsu's needs were more general (e.g., a multi-modal AI application), but for a RAG-focused code retrieval system, LlamaIndex's specialization is an advantage.

### 3.3 LangChain / LangGraph

| Attribute | Detail |
|---|---|
| **License** | MIT |
| **GitHub stars** | 130,768 |
| **Forks** | 21,537 |
| **Primary language** | Python, JavaScript |
| **Latest version** | Active development (March 2026) |
| **Maintainer** | LangChain Inc. |

**What it is:** An agent engineering platform for building LLM-powered applications. LangChain provides the component library; LangGraph provides the stateful orchestration layer for building agents as graphs.

**Architecture:** LangChain Expression Language (LCEL) for declarative chain composition; LangGraph for stateful multi-step agent workflows. Broad integration ecosystem (LLMs, vector stores, tools, retrievers).

**Strengths for Kenjutsu:**

1. **Largest community.** 130K+ stars, massive ecosystem, extensive documentation and examples.
2. **LangGraph agent framework.** If Kenjutsu needs agentic multi-hop search (Layer 3 of the context pipeline), LangGraph provides production-grade stateful agent orchestration.
3. **Broad integration coverage.** Supports most LLM providers, vector stores, and tools.
4. **LCEL composability.** Chains support streaming, async, batch, and routing out of the box.
5. **LangSmith observability.** Production tracing and debugging for LLM applications.

**Weaknesses:**

1. **Retrieval is not the core mission.** LangChain treats RAG as one capability among many (agents, tools, memory, chat). Less depth in retrieval-specific primitives compared to LlamaIndex.
2. **More code for the same RAG task.** Benchmarks consistently show LlamaIndex requires less code for equivalent RAG functionality. The gap grows with more data sources.
3. **Abstraction instability.** LangChain has undergone significant architectural changes (chains → LCEL → LangGraph), creating churn for users tracking the latest patterns.
4. **Complexity for retrieval-only use cases.** The agent/tool/memory abstractions add overhead when the primary need is retrieval composition.
5. **No built-in hierarchical indexing or auto-merging.** These retrieval-specific features require custom implementation.

**Fit for Kenjutsu: Moderate.** LangChain's strength is agent orchestration, not retrieval pipeline composition. For Kenjutsu's core retrieval needs, LlamaIndex provides more out of the box with less code. However, LangGraph is a strong candidate for the agentic search layer (Layer 3) if Kenjutsu needs multi-step reasoning about code dependencies. The recommended hybrid pattern — LlamaIndex for retrieval, LangGraph for agentic orchestration — is increasingly common in production systems.

### 3.4 Microsoft Semantic Kernel

| Attribute | Detail |
|---|---|
| **License** | MIT |
| **GitHub stars** | 27,531 |
| **Forks** | 4,520 |
| **Primary language** | C# (primary), Python, Java |
| **Latest version** | Active development (March 2026) |
| **Maintainer** | Microsoft |

**What it is:** An SDK for integrating AI capabilities into applications, centered on plugins, planners, and memory. Part of the broader Microsoft AI ecosystem (Azure OpenAI, Azure AI Search, Copilot).

**Architecture:** Three core concepts: Plugins (encapsulate AI capabilities as functions), Planners (orchestrate multi-step operations), Memory (semantic memory for context/RAG). Connectors for various AI services and data stores.

**Strengths for Kenjutsu:**

1. **Enterprise backing.** Microsoft maintains it actively, with strong documentation and support.
2. **Plugin architecture.** Clean extensibility model through plugins — custom retrievers could be implemented as plugins.
3. **Azure integration.** Deep integration with Azure AI Search, Azure OpenAI — advantageous if Kenjutsu uses Azure infrastructure.
4. **Multi-language support.** C#, Python, Java — though Python is not the primary implementation language.

**Weaknesses:**

1. **C#-first design.** Python support exists but lags behind C#. The most mature features, examples, and community support target .NET. Kenjutsu's stack is Python.
2. **Azure-centric ecosystem.** While it supports non-Azure services, the tightest integrations and best documentation assume Azure. Kenjutsu should remain cloud-agnostic.
3. **RAG is not the core mission.** Semantic Kernel focuses on AI orchestration broadly (planners, plugins, agents). RAG support exists but with fewer retrieval-specific primitives than LlamaIndex or even Haystack.
4. **Fewer retrieval-specific features.** No built-in hybrid search composition, no hierarchical indexing, no reranking pipeline. The TextSearchProvider is basic compared to LlamaIndex's retrieval stack.
5. **Smaller Python community.** Most community examples and third-party integrations target C#/.NET.

**Fit for Kenjutsu: Weak.** Semantic Kernel is optimized for the Microsoft/.NET ecosystem. Its Python support is secondary, its RAG capabilities are basic compared to LlamaIndex, and its Azure-centric design adds friction for a cloud-agnostic Python application. If Kenjutsu were a .NET application running on Azure, Semantic Kernel would be a strong candidate. It is not.

### 3.5 DSPy (Stanford NLP)

| Attribute | Detail |
|---|---|
| **License** | MIT |
| **GitHub stars** | 33,084 |
| **Forks** | 2,724 |
| **Primary language** | Python |
| **Latest version** | v2.6.x (March 2026) |
| **Maintainer** | Stanford NLP Group |

**What it is:** A framework for programming (not prompting) language models. DSPy defines AI programs as compositions of declarative modules, then uses optimizers to automatically generate prompts and fine-tune weights.

**Architecture:** Signatures (input/output specifications) → Modules (strategies for invoking LMs) → Optimizers (automatically compile programs into effective prompts). Focus is on prompt optimization and systematic LLM programming.

**Strengths for Kenjutsu:**

1. **Prompt optimization.** DSPy's optimizers (MIPROv2, COPRO, BootstrapFewShot) automatically find effective prompts — valuable for tuning review generation quality.
2. **Declarative approach.** Define what the LLM should do (input/output types), let DSPy figure out how to prompt it. Reduces manual prompt engineering.
3. **Evaluation-driven development.** Built-in support for metrics and optimization loops — aligns with Kenjutsu's need to minimize false positives.
4. **Academic rigor.** Peer-reviewed research (ICLR), principled approach to LLM programming.
5. **Growing ecosystem.** 33K+ stars, 500+ dependent projects.

**Weaknesses:**

1. **Not a retrieval framework.** DSPy is about programming LLMs, not building retrieval pipelines. It can use retrievers as components, but provides no retrieval infrastructure (no indexing, no vector store abstraction, no chunking strategies).
2. **No data ingestion or indexing.** No equivalent to LlamaIndex's document loaders, node parsers, or index management. You must bring your own retrieval layer.
3. **Different problem domain.** DSPy optimizes the LLM interaction layer; Kenjutsu's primary challenge is the retrieval layer. DSPy solves a real problem for Kenjutsu (prompt optimization for review generation), but not the retrieval problem.
4. **Steep learning curve.** The declarative/compilation model is powerful but unfamiliar. The mental model differs significantly from traditional pipeline frameworks.
5. **Less mature ecosystem.** Fewer integrations and production deployment examples compared to LlamaIndex or LangChain.

**Fit for Kenjutsu: Complementary, not foundational.** DSPy is the wrong tool for building a retrieval pipeline — it provides no indexing, chunking, or vector store infrastructure. However, it could be valuable for optimizing Kenjutsu's review generation layer (the LLM calls that produce review comments from retrieved context). The right architecture is: LlamaIndex for retrieval + DSPy for review generation optimization. This is a Layer 3 concern, not a foundation choice.

### 3.6 txtai (NeuML)

| Attribute | Detail |
|---|---|
| **License** | Apache-2.0 |
| **GitHub stars** | 12,324 |
| **Forks** | 788 |
| **Primary language** | Python |
| **Latest version** | Active development (March 2026) |
| **Maintainer** | NeuML |

**What it is:** An all-in-one embeddings database combining vector storage, text processing pipelines, and LLM orchestration. Unified interface for semantic search, RAG, and workflow orchestration.

**Architecture:** Embeddings database at the core — union of vector indexes (sparse + dense), graph networks, and relational databases. Pipelines for processing; workflows for orchestration; agents for autonomous operation.

**Strengths for Kenjutsu:**

1. **Integrated embeddings database.** Vector search with SQL, graph analysis, and topic modeling in a single system — simpler operational model than separate vector DB + framework.
2. **Hybrid search built-in.** Sparse (BM25) + dense (vector) search out of the box.
3. **Lightweight.** Fewer abstractions than LlamaIndex or LangChain — less overhead, faster to get started.
4. **Self-contained.** Can run entirely locally without external services.
5. **Apache-2.0 license.** No commercial restrictions.

**Weaknesses:**

1. **Much smaller ecosystem.** 12K stars, 788 forks — an order of magnitude smaller than LlamaIndex or LangChain. Fewer integrations, fewer community examples, fewer production deployment reports.
2. **Limited extension points.** Less documented patterns for custom chunking, custom retrievers, or composing multiple retrieval strategies compared to LlamaIndex.
3. **Fewer vector store options.** The integrated database is convenient but limits flexibility. Harder to swap to Qdrant or pgvector if needed.
4. **Single maintainer risk.** Smaller team than LlamaIndex (LlamaIndex Inc.) or Haystack (deepset GmbH). Bus factor is a concern for a production dependency.
5. **Less retrieval depth.** No hierarchical indexing, no auto-merging retriever, no sub-question decomposition. Designed for simpler use cases.

**Fit for Kenjutsu: Weak.** txtai is a good choice for simpler RAG applications where an integrated, self-contained system is valued. Kenjutsu's multi-signal retrieval pipeline requires composability and extensibility that txtai does not provide at the same depth as LlamaIndex or Haystack. The smaller ecosystem also increases risk for a production system.

---

## 4. Comparative Matrix

| Dimension | LlamaIndex | Haystack | LangChain | Semantic Kernel | DSPy | txtai |
|---|---|---|---|---|---|---|
| **License** | MIT | Apache-2.0 | MIT | MIT | MIT | Apache-2.0 |
| **GitHub stars** | 47.9K | 24.6K | 130.8K | 27.5K | 33.1K | 12.3K |
| **Primary focus** | RAG / data retrieval | AI orchestration | Agent engineering | AI SDK (Microsoft) | LLM programming | Embeddings DB |
| **RAG depth** | Deep (core mission) | Good (one capability) | Moderate (one of many) | Basic | None (bring your own) | Moderate |
| **Custom chunking** | NodeParser interface | Custom component | Custom splitter | Plugin | N/A | Limited |
| **Custom retrievers** | BaseRetriever interface | Custom component | Custom retriever class | Plugin | Retriever module | Limited |
| **Hybrid search (BM25+vector)** | Built-in, configurable | Built-in | Requires assembly | Basic | N/A | Built-in |
| **Hierarchical indexing** | Built-in | Custom component | Custom | No | N/A | No |
| **Reranking** | Built-in integrations | Built-in (LLMRanker) | Available | Limited | N/A | Limited |
| **Query routing** | Built-in | Pipeline branching | LCEL routing | Planner | N/A | No |
| **Vector store integrations** | 50+ | 15+ | 30+ | 10+ (Azure-centric) | Bring your own | Integrated DB |
| **Embedding model flexibility** | Excellent (50+ models) | Good | Good | Good (Azure focus) | Bring your own | Good |
| **Incremental indexing** | Supported | Supported | Manual | Limited | N/A | Supported |
| **Evaluation tools** | Built-in | RAGAS integration | LangSmith | Limited | Built-in (core strength) | Limited |
| **Python maturity** | Primary language | Primary language | Primary language | Secondary (C# first) | Primary language | Primary language |
| **Abstraction overhead** | Medium-high | Medium | Medium-high | Medium | Low | Low |
| **Learning curve** | Moderate | Moderate-steep | Moderate | Moderate | Steep (new paradigm) | Low |
| **Fit for Kenjutsu** | **Strong** | Good | Moderate | Weak | Complementary | Weak |

---

## 5. Recommendation

### Primary: LlamaIndex as orchestration layer

LlamaIndex is the strongest foundation for Kenjutsu's retrieval pipeline because its design problem matches our design problem: composing multiple retrieval strategies over custom-indexed data to maximize the relevance of what gets fed to the LLM.

**Concrete integration plan:**

| Kenjutsu Component | LlamaIndex Extension Point | Custom or Built-in |
|---|---|---|
| Function-level code chunking | Custom NodeParser (tree-sitter) | **Custom** — implement `CodeNodeParser` using tree-sitter to chunk at function/class boundaries |
| Import graph retrieval | Custom BaseRetriever | **Custom** — tree-sitter import resolution, returns dependency nodes |
| Co-change retrieval | Custom BaseRetriever | **Custom** — git log mining, returns historically coupled files |
| Test file matching | Custom BaseRetriever | **Custom** — path heuristic (`*_test.py` ↔ `*.py`) |
| Semantic code search | VectorIndexRetriever + embedding integration | **Built-in** — configure with Voyage-code-3 |
| Keyword search | BM25Retriever | **Built-in** — BM25 over code identifier index |
| Hybrid search composition | QueryFusionRetriever | **Built-in** — combines multiple retrievers with reciprocal rank fusion |
| Reranking | CohereRerank or SentenceTransformerRerank | **Built-in** — cross-encoder reranking integration |
| Query routing | RouterQueryEngine | **Built-in** — route simple PRs to heuristics, complex PRs to full retrieval |
| Vector storage | QdrantVectorStore or PGVectorStore | **Built-in** — swap with configuration change |
| Incremental re-indexing | Document management with doc_id tracking | **Built-in** — upsert changed documents |

**Four custom components, seven built-in.** This is the key advantage: LlamaIndex handles the retrieval infrastructure; we focus custom effort on the code-specific differentiation.

### Why not Haystack?

Haystack is the closest competitor. Its component model is architecturally clean and its production infrastructure is strong. But for Kenjutsu specifically:

- Haystack has **fewer retrieval-specific built-ins** — hierarchical indexing, auto-merging retriever, sub-question decomposition, and query fusion would all need to be built as custom components. In LlamaIndex, they are configuration.
- Haystack's **ecosystem is smaller** (24.6K vs 47.9K stars, fewer integrations). For a retrieval-focused system, the breadth of LlamaIndex's vector store and embedding model integrations matters.
- If Kenjutsu were a broader AI platform (not retrieval-focused), Haystack's general orchestration model would be more compelling.

### Why not LangChain?

LangChain has the largest community but treats retrieval as one feature among many. For the same RAG task, LlamaIndex consistently requires less code and provides more retrieval-specific primitives. However, **LangGraph is a strong complement** for Kenjutsu's agentic search layer (Layer 3) — stateful multi-hop reasoning about code dependencies. The pattern of LlamaIndex for retrieval + LangGraph for agents is well-established in production systems.

### Why not Semantic Kernel, DSPy, or txtai?

- **Semantic Kernel:** C#-first, Azure-centric. Wrong ecosystem for a Python/cloud-agnostic project.
- **DSPy:** Not a retrieval framework. Valuable for prompt optimization (review generation quality), not for building retrieval pipelines. Consider as a Layer 3 complement for review quality tuning.
- **txtai:** Too small an ecosystem and too limited in extensibility for Kenjutsu's multi-signal pipeline.

### Why not build entirely from scratch?

Building from scratch gives full control but means reimplementing:
- Vector store abstraction (connection pooling, batching, error handling across stores)
- Hybrid search composition (score normalization, reciprocal rank fusion)
- Embedding model abstraction (batching, rate limiting, model-specific tokenization)
- Query routing logic
- Incremental indexing with document tracking
- Reranking pipeline integration

None of these provide competitive advantage. They are infrastructure that LlamaIndex handles well. Custom effort should focus on the four code-specific components where Kenjutsu's differentiation lives.

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LlamaIndex API churn between versions | Medium | Medium | Pin major version. Abstract behind internal interfaces (`KenjutsuRetriever` wraps `BaseRetriever`). Monitor release notes. |
| Custom component maintenance burden | Medium | Medium | Keep components small, well-tested, and focused. AST parsing via tree-sitter is deterministic — fewer edge cases than LLM-based components. |
| Voyage-code-3 deprecation or pricing change | Low | Medium | LlamaIndex's embedding abstraction makes model swap a config change. Evaluate alternatives annually. |
| LlamaIndex ecosystem shifts toward LlamaCloud | Low | Low | MIT license ensures OSS remains available. LlamaCloud is additive (managed service), not a replacement. |
| Framework becomes unmaintained | Very Low | High | LlamaIndex has 47.9K stars, commercial backing (LlamaIndex Inc.), and MIT license. If unmaintained, fork or migrate to Haystack (similar concepts, different API). |
| Abstraction overhead in hot path | Low | Low | Code review is not latency-critical (seconds, not milliseconds). Profile before optimizing. |

---

## 7. What to Watch

1. **Haystack code-specific components.** If deepset or the community builds tree-sitter-based components for Haystack, it could close the gap with LlamaIndex.
2. **DSPy retrieval integration.** DSPy's roadmap includes deeper retrieval support. If DSPy adds retrieval infrastructure, it could become a unified framework for both retrieval and generation optimization.
3. **LangChain retrieval improvements.** LangChain is actively investing in retrieval. Watch for hierarchical indexing or built-in code chunking support.
4. **Code-specific RAG frameworks.** Emerging projects like code-graph-rag (tree-sitter + knowledge graphs) may provide purpose-built alternatives. Monitor for production-readiness.
5. **Embedding model evolution.** If a model significantly outperforms Voyage-code-3 for code retrieval, the embedding swap should be easy with LlamaIndex's abstraction.

---

## 8. Decision Summary

| Question | Answer |
|---|---|
| **Is LightRAG viable for Kenjutsu?** | No. Graph-RAG systems use LLM entity extraction designed for prose, not code. |
| **Which framework should Kenjutsu use?** | LlamaIndex — deepest retrieval primitives, largest integration ecosystem, natural extension points for code-specific components. |
| **What is the runner-up?** | Haystack — architecturally clean, production-grade, but requires more custom code for retrieval-specific features. |
| **Should we use LangChain?** | Not as the retrieval foundation. Consider LangGraph as a complement for agentic search (Layer 3). |
| **How much custom code is needed?** | Four custom components (tree-sitter NodeParser, import graph retriever, co-change retriever, test file matcher). Seven retrieval capabilities are built-in. |
| **Primary risk?** | LlamaIndex API churn. Mitigated by version pinning and internal abstraction. |

---

## Sources

- [LlamaIndex — GitHub](https://github.com/run-llama/llama_index) — 47,912 stars, MIT license
- [Haystack — GitHub (deepset)](https://github.com/deepset-ai/haystack) — 24,593 stars, Apache-2.0 license
- [LangChain — GitHub](https://github.com/langchain-ai/langchain) — 130,768 stars, MIT license
- [Semantic Kernel — GitHub (Microsoft)](https://github.com/microsoft/semantic-kernel) — 27,531 stars, MIT license
- [DSPy — GitHub (Stanford NLP)](https://github.com/stanfordnlp/dspy) — 33,084 stars, MIT license
- [txtai — GitHub (NeuML)](https://github.com/neuml/txtai) — 12,324 stars, Apache-2.0 license
- [LangChain vs LlamaIndex (2026): Complete Production RAG Comparison](https://blog.premai.io/langchain-vs-llamaindex-2026-complete-production-rag-comparison/)
- [Production RAG in 2026: LangChain vs LlamaIndex](https://rahulkolekar.com/production-rag-in-2026-langchain-vs-llamaindex/)
- [LangChain vs LlamaIndex (2026): The RAG Framework Wars Are Over](https://leonstaff.com/blogs/langchain-vs-llamaindex-rag-wars/)
- [The Best RAG Frameworks for Building Enterprise GenAI in 2026](https://www.tredence.com/blog/top-rag-frameworks)
- [15 Best Open-Source RAG Frameworks in 2026](https://www.firecrawl.dev/blog/best-open-source-rag-frameworks)
- [Custom RAG Pipeline for Context-Powered Code Reviews — Qodo](https://www.qodo.ai/blog/custom-rag-pipeline-for-context-powered-code-reviews/)
- [How I Built CodeRAG with Dependency Graph Using Tree-Sitter](https://medium.com/@shsax/how-i-built-coderag-with-dependency-graph-using-tree-sitter-0a71867059ae)
- [Haystack Documentation](https://docs.haystack.deepset.ai/docs/intro)
- [Semantic Kernel — RAG with Agents](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-rag)
- [DSPy — RAG Tutorial](https://dspy.ai/tutorials/rag/)
