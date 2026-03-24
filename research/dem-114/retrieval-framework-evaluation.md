# Retrieval Framework Evaluation for Kenjutsu

- **Status:** review
- **Author:** Chief Architect
- **Date:** 2026-03-23
- **Issue:** DEM-114
- **Parent:** DEM-113
- **Version:** 3.1 (consolidates v1 deep-dive content into appendices; removes stale top-level file)

---

## Executive Summary

Kenjutsu needs a retrieval pipeline that can surface contextually relevant code given a PR diff. This requires code-specific capabilities — AST parsing, import graph traversal, co-change analysis, function-level chunking — that no prebuilt system offers out of the box. The question is not "which system solves code retrieval for us?" but "which framework is the best foundation for building our custom code retrieval pipeline?"

This evaluation covers **ten frameworks** across three categories:

1. **Graph-RAG systems** (LightRAG) — category mismatch for code retrieval
2. **RAG orchestration frameworks** (LlamaIndex, Haystack) — retrieval is the core mission
3. **Agent frameworks with RAG capabilities** (Agno, LangChain, Mastra, Pydantic AI, AWS Strands Agents, Semantic Kernel, DSPy)

The board specifically requested evaluation of **Agno, Pydantic AI, Mastra, and AWS Strands Agents** to ensure the comparison includes the current generation of AI frameworks, not just established players.

**Recommendation: LlamaIndex as the orchestration layer.** After evaluating all ten frameworks — including the four modern agent frameworks the board requested — LlamaIndex remains the strongest foundation for Kenjutsu's retrieval pipeline. The modern agent frameworks (Agno, Pydantic AI, Strands) solve a different problem: agent orchestration. Agno comes closest to competing, with built-in AST code chunking and hybrid search, but lacks the advanced retrieval patterns (hierarchical indexing, auto-merging retrieval, query routing, sub-question decomposition) that Kenjutsu's multi-signal pipeline requires. Mastra has solid RAG capabilities but is TypeScript-only, incompatible with Kenjutsu's Python stack.

---

## 1. What Kenjutsu Needs from a Retrieval Framework

Before evaluating frameworks, we define what Kenjutsu actually requires. These requirements are derived independently so the evaluation stands on its own. (The DEM-104 research provides background on Kenjutsu's broader context pipeline architecture but is not treated as prescriptive.)

### 1.1 The Retrieval Problem

When a PR is opened, Kenjutsu must retrieve the code context most relevant to reviewing the changes:

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

### 2.1 LightRAG Assessment

LightRAG (HKUDS, University of Hong Kong, MIT license, 30.3K GitHub stars) is a graph-enhanced RAG system that builds knowledge graphs from documents via LLM-based entity extraction. It is well-designed for natural language document retrieval with relationship-aware queries.

**Why it does not fit Kenjutsu:**

1. **Entity extraction assumes prose.** LightRAG's LLM extracts subjects, objects, and relationships from sentences. Code has a fundamentally different structure: functions, classes, imports, type hierarchies. LLM extraction will miss structural relationships that AST parsing captures deterministically.
2. **Fixed-token chunking splits code at wrong boundaries.** LightRAG's default 1200-token chunking will split functions mid-body. Code must be chunked at syntactic boundaries.
3. **No code-specific retrieval signals.** No co-change analysis, no test-file matching, no type-hierarchy traversal, no import graph extraction.
4. **Embedding model lock-in.** Switching embedding models requires deleting vector tables and full re-index.

**The same fundamental mismatch applies to all graph-RAG systems** (Microsoft GraphRAG, R2R, Cognee) that rely on LLM-based entity extraction. For code, the graph that matters is derived from **AST parsing** (tree-sitter), not LLM entity extraction:

| Signal | Source | Cost |
|---|---|---|
| Function/class dependencies | tree-sitter AST + import resolution | Free (static analysis) |
| Call graphs | tree-sitter cross-reference | Free (static analysis) |
| Co-changed files | git log mining | Free (git history) |
| Type hierarchies | tree-sitter + language-specific queries | Free (static analysis) |
| Similar implementations | Embedding similarity search | Medium (vector query) |

**Bottom line:** Graph-RAG systems solve document retrieval. Kenjutsu needs code retrieval. These are different problems.

---

## 3. The Modern AI Framework Landscape: Retrieval vs. Agent Frameworks

The board raised an important question: are established frameworks like LangChain and Haystack being superseded by newer entrants like Agno, Pydantic AI, Mastra, and AWS Strands Agents?

The answer requires distinguishing two categories of frameworks that solve different problems:

### 3.1 RAG Orchestration Frameworks

**Examples:** LlamaIndex, Haystack

These frameworks treat **retrieval as the core design problem**. They provide purpose-built abstractions for every stage of a retrieval pipeline: document loading → chunking → embedding → index construction → retrieval → reranking → response synthesis. Extension points are retrieval-oriented (custom node parsers, custom retrievers, custom postprocessors).

### 3.2 Agent Frameworks

**Examples:** Agno, Pydantic AI, Mastra, AWS Strands Agents, LangChain/LangGraph

These frameworks treat **agent orchestration as the core design problem**. They provide abstractions for LLM-driven tool use, multi-agent coordination, structured output, and workflow execution. Some include RAG capabilities, but retrieval is one feature among many — not the architectural center of gravity.

### 3.3 Why This Distinction Matters for Kenjutsu

Kenjutsu's primary technical challenge is **retrieval pipeline composition** — combining AST-derived signals, git history, semantic similarity, and keyword matching into a pipeline that maximizes the relevance of context fed to the LLM for code review. This is a retrieval problem, not an agent orchestration problem.

An agent framework can serve as the layer *on top of* a retrieval pipeline (the agent reasons over retrieved context), but it does not replace the retrieval pipeline itself. Choosing an agent framework as the foundation would mean building all retrieval infrastructure from scratch, using the agent framework only for the final orchestration step.

This is not a "modern vs. legacy" distinction. LlamaIndex (47.9K stars, MIT, active weekly releases, commercial backing) is as current as any framework evaluated here. The question is which *type* of framework matches Kenjutsu's core problem.

---

## 4. Framework Evaluations

### 4.1 LlamaIndex — RAG Orchestration

| Attribute | Detail |
|---|---|
| **License** | MIT |
| **GitHub stars** | 47,912 |
| **Primary language** | Python |
| **Latest version** | v0.14.x (March 2026) |
| **Maintainer** | LlamaIndex Inc. |
| **Category** | RAG orchestration framework |

**What it is:** A data framework purpose-built for connecting LLMs with private data through RAG. Retrieval is the core design problem.

**Architecture:** Documents → Nodes → Index (vector, keyword, knowledge graph, or custom) → QueryEngine → Response. 300+ integration packages.

**Strengths for Kenjutsu:**

1. **Deepest retrieval primitives.** Hierarchical indexing, hybrid search (BM25 + vector), recursive retrieval, auto-merging retriever, sub-question decomposition, and query routing — all built-in and composable.
2. **NodeParser interface.** The natural extension point for custom chunking. A tree-sitter-based NodeParser that chunks at function/class boundaries is a well-documented pattern.
3. **Custom retrievers.** The BaseRetriever interface lets us implement import graph traversal, co-change analysis, and test-file matching as first-class retrieval components that compose with built-in retrievers.
4. **Largest RAG integration ecosystem.** 300+ integrations including Voyage-code-3, Qdrant, pgvector, Cohere Rerank.
5. **Hybrid search built-in.** BM25 + vector retrieval with configurable weighting via QueryFusionRetriever.
6. **Evaluation tools.** Built-in RAGAS-style evaluation metrics.
7. **Code-specific primitives.** `CodeSplitter` and `CodeHierarchyNodeParser` (tree-sitter-based) provide a head start on code chunking.

**Weaknesses:**

1. **Abstraction overhead.** Deep abstraction layers add performance overhead vs. direct vector DB access. Debugging retrieval quality through these layers requires deeper framework knowledge than more explicit pipeline models (as noted by Technical Planner A review).
2. **API churn.** Breaking changes between minor versions have historically been disruptive. Mitigate by pinning major version and abstracting behind internal interfaces.
3. **LlamaCloud commercial pressure.** VC-backed OSS trend: monitor whether new retrieval primitives land in LlamaCloud before the open-source library (risk identified by Technical Planner A review).

**Fit for Kenjutsu: Strong.** LlamaIndex treats RAG as the core problem, which is Kenjutsu's core problem. The NodeParser and BaseRetriever interfaces are natural extension points for code-specific components.

### 4.2 Haystack (deepset) — RAG Orchestration

| Attribute | Detail |
|---|---|
| **License** | Apache-2.0 |
| **GitHub stars** | 24,593 |
| **Primary language** | Python |
| **Latest version** | v2.26 (March 2026) |
| **Maintainer** | deepset GmbH |
| **Category** | AI orchestration framework with strong RAG focus |

**What it is:** An AI orchestration framework for building production-ready LLM applications with explicit control over retrieval, routing, memory, and generation.

**Architecture:** Component-based DAG pipelines with standard input/output interfaces. Components compose into pipelines that can branch, loop, and route.

**Strengths for Kenjutsu:**

1. **Technology-agnostic component model.** Each retrieval signal would be a custom component with a standard interface. Clean separation of concerns.
2. **Production-grade infrastructure.** Serializable pipelines, cloud-agnostic deployment, logging, monitoring.
3. **Explicit pipeline model.** The DAG pipeline makes debugging retrieval quality more transparent than LlamaIndex's deeper abstractions.
4. **Strong evaluation framework.** RAGAS integration for measuring retrieval quality.
5. **Apache-2.0 license.** No commercial restrictions.

**Weaknesses:**

1. **Fewer retrieval-specific built-ins** than LlamaIndex. Hierarchical indexing, auto-merging retriever, and sub-question decomposition would need custom implementation.
2. **Smaller ecosystem.** 24.6K vs 47.9K stars, fewer integrations.
3. **Higher-level orchestration focus.** Haystack is a general AI orchestration framework — less depth in retrieval-specific primitives.

**Fit for Kenjutsu: Good.** Strong runner-up. Architecturally clean, better debugging transparency than LlamaIndex. But requires more custom retrieval code.

### 4.3 Agno (formerly Phidata) — Agent Framework with RAG

| Attribute | Detail |
|---|---|
| **License** | Apache-2.0 |
| **GitHub stars** | 38,900 |
| **Primary language** | Python |
| **Latest version** | v2.5.10 (March 2026) |
| **Maintainer** | Agno AGI |
| **Category** | Agent framework with substantial RAG subsystem |
| **PyPI downloads** | ~1.5M/month |

**What it is:** An agent framework ("Build, run, manage agentic software at scale") with a first-class knowledge/retrieval subsystem. The most retrieval-capable of the modern agent frameworks.

**Architecture:** Agent-first — agents are the core primitive. Knowledge is attached to agents via a `Knowledge` class that manages content ingestion, chunking, embedding, vector storage, and retrieval. A `KnowledgeProtocol` (Python structural typing) allows fully custom knowledge implementations.

**Strengths for Kenjutsu:**

1. **AST-based code chunking.** Ships with `CodeChunking` strategy that uses Chonkie/tree-sitter to split at function/class boundaries. Supports Python, TypeScript, JavaScript, Go, Rust, Java, and more. This is directly relevant to Kenjutsu.
2. **Hybrid search with RRF.** PgVector backend uses PostgreSQL `ts_query` for BM25 + HNSW for vector, fused via Reciprocal Rank Fusion.
3. **17+ vector store integrations.** Unified `VectorDb` ABC: PgVector, Pinecone, Qdrant, Weaviate, Chroma, LanceDB, Milvus, MongoDB, and more.
4. **Reranking support.** Cohere, AWS Bedrock, Infinity, SentenceTransformer.
5. **Clean extension points.** `ChunkingStrategy` ABC, `KnowledgeProtocol`, `VectorDb` ABC, `Reranker` base class.
6. **Growing fast.** 38.9K stars, active weekly releases, substantial community.

**Weaknesses for Kenjutsu:**

1. **No advanced retrieval patterns.** No hierarchical indexing, no auto-merging retrieval, no recursive retrieval, no sentence-window retrieval, no sub-question decomposition. These are the patterns that compose multiple retrieval signals into a unified pipeline — exactly what Kenjutsu needs.
2. **No query routing at retrieval level.** Agent teams provide agent-level routing, but there is no `RouterQueryEngine` equivalent for routing different queries to different retrieval strategies.
3. **No built-in evaluation.** No RAG evaluation framework for measuring retrieval quality over time.
4. **Incremental indexing has known friction.** `upsert`/`skip_if_exists` coupling has open issues (GitHub #5295). No diff-aware incremental re-indexing.
5. **Agent-mediated retrieval.** Retrieval goes through the agent loop (LLM decides to call knowledge tools). For a code review pipeline that needs deterministic, high-throughput retrieval, this adds latency and non-determinism vs. direct retrieval pipeline execution.
6. **Smaller download base.** ~1.5M/month vs LlamaIndex's ~9.8M+.

**Fit for Kenjutsu: Moderate.** Agno is the strongest agent framework for RAG and its AST code chunking is genuinely relevant. But Kenjutsu's core problem is retrieval pipeline composition, not agent orchestration. Agno would require building the advanced retrieval patterns that LlamaIndex provides as configuration. The code chunking implementation is worth studying as a reference.

### 4.4 LangChain / LangGraph — Agent Framework with RAG

| Attribute | Detail |
|---|---|
| **License** | MIT |
| **GitHub stars** | 130,768 |
| **Primary language** | Python, JavaScript |
| **Maintainer** | LangChain Inc. |
| **Category** | Agent engineering platform |

**What it is:** An agent engineering platform. LangChain provides the component library; LangGraph provides stateful orchestration for multi-step agent workflows.

**Strengths for Kenjutsu:**

1. **Largest community.** 130K+ stars, extensive ecosystem.
2. **LangGraph agent framework.** Strong candidate for agentic multi-hop search (Layer 3 of context pipeline).
3. **LangSmith observability.** Production tracing and debugging.

**Weaknesses for Kenjutsu:**

1. **Retrieval is not the core mission.** RAG is one capability among many. Less depth in retrieval-specific primitives than LlamaIndex.
2. **More code for equivalent RAG.** Benchmarks consistently show LlamaIndex requires less code for the same retrieval functionality.
3. **No built-in hierarchical indexing or auto-merging.** These require custom implementation.

**Fit for Kenjutsu: Moderate.** Not the right foundation for the retrieval pipeline, but LangGraph is a strong complement for the agentic search layer. The pattern of LlamaIndex for retrieval + LangGraph for agents is well-established in production.

### 4.5 Pydantic AI — Agent Framework (Minimal RAG)

| Attribute | Detail |
|---|---|
| **License** | MIT |
| **GitHub stars** | 15,700 |
| **Primary language** | Python |
| **Latest version** | v1.70.0 (March 2026) |
| **Maintainer** | Pydantic Services Inc. (Samuel Colvin) |
| **Category** | Type-safe agent framework |
| **PyPI downloads** | ~15.2M/month |

**What it is:** A GenAI agent framework built "the Pydantic way" — type-safe, minimal, FastAPI-like developer experience. Not a retrieval framework.

**RAG approach:** RAG is treated as "just another tool." The official docs state: "Function tools are basically the 'R' of RAG." You write a Python function that queries your own database and register it as a tool. Pydantic AI provides no retrieval pipeline abstractions — no chunking, no indexing, no vector store abstraction, no hybrid search, no reranking, no query routing.

**What it does well:** Type-safe structured output validation, dependency injection, MCP/A2A protocol support, rapid weekly releases. Very high download volume (~15.2M/month) driven by the Pydantic brand.

**Fit for Kenjutsu: Complementary, not foundational.** Pydantic AI would require building the entire retrieval pipeline from scratch with no framework support. It could serve as the agent layer *on top of* a LlamaIndex retrieval pipeline — its type-safe structured output and dependency injection are useful for the "reasoning over retrieved context" stage. But it cannot be the retrieval foundation.

### 4.6 Mastra — Agent Framework with RAG (TypeScript)

| Attribute | Detail |
|---|---|
| **License** | Apache-2.0 |
| **GitHub stars** | 22,260 |
| **Primary language** | TypeScript |
| **Latest version** | @mastra/core@1.14.0 (March 2026) |
| **Maintainer** | Mastra AI (ex-Gatsby team, YC-backed) |
| **Category** | Agent framework with integrated RAG |

**What it is:** A TypeScript-first agent framework with solid RAG capabilities including 9 chunking strategies (with language-aware code splitting for 30 languages), 14 vector store backends, LLM-based reranking, and Graph RAG.

**RAG capabilities:** Mastra has meaningful retrieval features — code-aware recursive chunking (regex-based, not AST), hybrid search via workspace BM25 + vector, reranking (Cohere, ZeroEntropy), and a `VectorStoreResolver` for dynamic routing. Its RAG subsystem is more capable than most agent frameworks.

**Fit for Kenjutsu: Not viable.** Mastra is **TypeScript-only**. Kenjutsu's stack is Python (FastAPI, tree-sitter, PyGithub). There is no Python version. This is a hard disqualifier regardless of RAG capability. If Kenjutsu were a TypeScript project, Mastra would deserve deeper evaluation — its RAG subsystem is the strongest among the agent frameworks after Agno.

### 4.7 AWS Strands Agents — Agent Framework (Minimal RAG)

| Attribute | Detail |
|---|---|
| **License** | Apache-2.0 |
| **GitHub stars** | 5,358 |
| **Primary language** | Python |
| **Latest version** | v1.32.0 (March 2026) |
| **Maintainer** | AWS |
| **Category** | Model-driven agent SDK |
| **Age** | 10 months (launched May 2025) |

**What it is:** An open-source agent framework from AWS built around model-driven tool use. The agent loop is minimal: the LLM decides which tools to call. Multi-agent patterns (Graph, Swarm, Workflow) are modeled as tools.

**RAG approach:** Retrieval is "just another tool" — a thin ~150-line wrapper around the `bedrock-agent-runtime.retrieve()` API. No chunking, no indexing, no vector store abstraction, no hybrid search, no reranking. The retrieval tools are **hardcoded to Amazon Bedrock Knowledge Bases** — if you want RAG without AWS, you build everything yourself.

**Fit for Kenjutsu: Not viable.** Zero retrieval infrastructure. AWS-locked for what little RAG exists. Very early stage (10 months, 5.4K stars, 30 contributors). The core SDK can run without AWS, but the retrieval capabilities cannot. Kenjutsu should remain cloud-agnostic.

### 4.8 Other Frameworks Evaluated

**Semantic Kernel (Microsoft)** — 27.5K stars, MIT. C#-first, Azure-centric SDK. Python support is secondary. RAG capabilities are basic compared to LlamaIndex. **Not viable:** wrong language ecosystem for a Python/cloud-agnostic project.

**DSPy (Stanford NLP)** — 33.1K stars, MIT. A framework for programming (not prompting) language models via declarative modules and automatic prompt optimization. **Not a retrieval framework** — provides no indexing, chunking, or vector store infrastructure. However, valuable as a **complement** for optimizing Kenjutsu's review generation quality (prompt optimization for the LLM calls that produce review comments from retrieved context).

---

## 5. Comparative Matrix

### 5.1 RAG Capability Comparison (All Frameworks)

| Dimension | LlamaIndex | Haystack | Agno | LangChain | Pydantic AI | Mastra | Strands | Semantic Kernel | DSPy |
|---|---|---|---|---|---|---|---|---|---|
| **Category** | RAG framework | AI orchestration | Agent + RAG | Agent platform | Agent framework | Agent + RAG | Agent SDK | AI SDK | LLM programming |
| **Language** | Python | Python | Python | Python/JS | Python | **TypeScript** | Python | C# (primary) | Python |
| **GitHub stars** | 47.9K | 24.6K | 38.9K | 130.8K | 15.7K | 22.3K | 5.4K | 27.5K | 33.1K |
| **RAG depth** | Deep (core) | Good | Moderate | Moderate | None | Good | None | Basic | None |
| **Custom chunking** | NodeParser | Component | ChunkingStrategy ABC | Splitter | None | 9 strategies | None | Plugin | N/A |
| **AST code chunking** | tree-sitter | Custom | tree-sitter (Chonkie) | Custom | None | Regex (30 langs) | None | None | N/A |
| **Custom retrievers** | BaseRetriever | Component | KnowledgeProtocol | Retriever class | Tool function | Tool config | Tool function | Plugin | Module |
| **Hybrid search** | Built-in | Built-in | Built-in (RRF) | Assembly | None | Built-in | None | Basic | N/A |
| **Hierarchical indexing** | Built-in | Custom | No | Custom | None | No | None | No | N/A |
| **Reranking** | Built-in | Built-in | Built-in | Available | None | Built-in | None | Limited | N/A |
| **Query routing** | Built-in | Pipeline | No (agent-level) | LCEL | None | Partial | None | Planner | N/A |
| **Vector store integrations** | 50+ | 15+ | 17+ | 30+ | None | 14 | Bedrock only | 10+ | BYO |
| **Incremental indexing** | Supported | Supported | Partial (issues) | Manual | None | Partial | N/A | Limited | N/A |
| **Evaluation tools** | Built-in | RAGAS | None | LangSmith | None | None | None | Limited | Built-in |
| **Fit for Kenjutsu** | **Strong** | Good | Moderate | Moderate | Complementary | Not viable (TS) | Not viable | Not viable (C#) | Complementary |

### 5.2 The "Modern vs. Legacy" Question

The board asked whether frameworks like LangChain and Haystack represent an older generation being displaced by newer entrants. Here is the evidence:

| Framework | First release | Latest release | Release cadence | Trend |
|---|---|---|---|---|
| LlamaIndex | 2022 | March 2026 | Weekly | Growing — 300+ integrations, commercial backing |
| Haystack | 2020 (v2 rewrite 2024) | March 2026 | Bi-weekly | Stable — major v2 modernization |
| LangChain | 2022 | March 2026 | Weekly | Pivoting toward LangGraph (agents) |
| Agno | 2024 (as Phidata) | March 2026 | Weekly | Growing fast — rebranded, expanding RAG |
| Pydantic AI | Oct 2024 | March 2026 | Weekly | Growing fast — Pydantic brand momentum |
| Mastra | Aug 2024 | March 2026 | Weekly | Growing — YC-backed |
| Strands | May 2025 | March 2026 | Weekly | Very early — AWS backing |

**Assessment:** The "modern vs. legacy" framing conflates two different market shifts:

1. **Agent frameworks are growing** — Agno, Pydantic AI, Strands are gaining adoption for building AI agents. This is real and important, but agents and retrieval pipelines are different problems.
2. **Retrieval frameworks are not being replaced** — LlamaIndex and Haystack continue to grow because nothing in the agent framework category provides equivalent retrieval depth. Many production systems combine both: a retrieval framework for the data pipeline + an agent framework for reasoning.

LlamaIndex is not "legacy." It is the current standard for retrieval pipeline composition, actively maintained with weekly releases and 300+ integrations. The newer agent frameworks address a different need — and for teams that need both, the standard pattern is to use them together, not to replace one with the other.

---

## 6. Recommendation

### Primary: LlamaIndex as orchestration layer

LlamaIndex is the strongest foundation for Kenjutsu's retrieval pipeline because its design problem matches our design problem: composing multiple retrieval strategies over custom-indexed data to maximize the relevance of what gets fed to the LLM.

**Concrete integration plan:**

| Kenjutsu Component | LlamaIndex Extension Point | Custom or Built-in |
|---|---|---|
| Function-level code chunking | Custom NodeParser (tree-sitter) | **Custom** — implement `CodeNodeParser` using tree-sitter |
| Import graph retrieval | Custom BaseRetriever | **Custom** — tree-sitter import resolution, returns dependency nodes |
| Co-change retrieval | Custom BaseRetriever | **Custom** — git log mining, returns historically coupled files |
| Test file matching | Custom BaseRetriever | **Custom** — path heuristic (`*_test.py` ↔ `*.py`) |
| Semantic code search | VectorIndexRetriever + embedding | **Built-in** — configure with Voyage-code-3 |
| Keyword search | BM25Retriever | **Built-in** — BM25 over code identifier index |
| Hybrid search composition | QueryFusionRetriever | **Built-in** — combines retrievers with reciprocal rank fusion |
| Reranking | CohereRerank or SentenceTransformerRerank | **Built-in** — cross-encoder reranking |
| Query routing | RouterQueryEngine | **Built-in** — route simple PRs to heuristics, complex to full retrieval |
| Vector storage | QdrantVectorStore or PGVectorStore | **Built-in** — swap with config change |
| Incremental re-indexing | Document management with doc_id tracking | **Built-in** — upsert changed documents |

**Four custom components, seven built-in.** This ratio is the key advantage: LlamaIndex handles retrieval infrastructure; we focus custom effort on code-specific differentiation.

### Why not Agno?

Agno is the strongest alternative and deserves serious consideration. Its AST-based code chunking (via Chonkie/tree-sitter) is directly relevant, and its `KnowledgeProtocol` is a clean extension point. However:

- Agno lacks **hierarchical indexing, auto-merging retrieval, query routing, and sub-question decomposition** — the retrieval composition patterns that let us combine multiple code signals into a unified pipeline. These would need to be built from scratch.
- Agno's retrieval is **agent-mediated** — the LLM decides when to call knowledge tools. Kenjutsu needs deterministic, high-throughput retrieval for every PR, not LLM-gated access to knowledge.
- Agno's incremental indexing has **known friction** (GitHub #5295). For a code review tool that must re-index on every PR push, this is a real concern.

**Study Agno's `CodeChunking` implementation** as a reference when building our tree-sitter NodeParser.

### Why not Haystack?

Haystack is the closest runner-up among retrieval frameworks. Its explicit DAG pipeline model offers better debugging transparency than LlamaIndex's deeper abstractions. However:

- Haystack has **fewer retrieval-specific built-ins.** Hierarchical indexing, auto-merging, and query fusion would need custom components. In LlamaIndex, they are configuration.
- **Smaller ecosystem** (24.6K vs 47.9K stars, fewer integrations). For a retrieval-focused system, LlamaIndex's breadth of vector store and embedding model integrations matters.

### Why not Pydantic AI, Strands, LangChain, or Mastra?

- **Pydantic AI:** No retrieval infrastructure at all. Excellent type-safe agent framework, but the entire retrieval pipeline would be built from scratch. Consider as a complement for structured LLM output validation.
- **AWS Strands Agents:** No retrieval infrastructure. AWS-locked for the minimal RAG it provides. Too early-stage (10 months, 30 contributors).
- **LangChain:** Retrieval is not the core mission. More code for equivalent RAG. However, **LangGraph** is a strong complement for agentic search (Layer 3). The pattern of LlamaIndex for retrieval + LangGraph for agents is well-established.
- **Mastra:** TypeScript-only. Hard disqualifier for a Python stack.

### Why not build entirely from scratch?

Building from scratch gives full control but means reimplementing:
- Vector store abstraction (connection pooling, batching, error handling)
- Hybrid search composition (score normalization, reciprocal rank fusion)
- Embedding model abstraction (batching, rate limiting, model-specific tokenization)
- Query routing logic
- Incremental indexing with document tracking
- Reranking pipeline integration

None of these provide competitive advantage. A **lightweight orchestration + direct vector DB** middle ground exists (identified by Technical Planner A review), but at Kenjutsu's retrieval complexity — four custom retrievers, hybrid search, reranking, query routing — the framework overhead is justified by the infrastructure it handles.

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LlamaIndex API churn between versions | Medium | Medium | Pin major version. Abstract behind internal interfaces (`KenjutsuRetriever` wraps `BaseRetriever`). |
| Debugging retrieval quality through LlamaIndex abstractions | Medium | Medium | Invest in evaluation metrics (RAGAS). Use LlamaIndex's built-in debugging tools. Consider Haystack for specific sub-pipelines if debugging becomes a bottleneck. |
| LlamaIndex → LlamaCloud commercial pressure | Low-Medium | Medium | Monitor whether new retrieval primitives land in LlamaCloud before OSS. MIT license ensures fork option. Haystack is migration target if needed. |
| Custom component testing burden (4 components × API churn) | Medium | Medium | Pin LlamaIndex version. Integration test suite against NodeParser and BaseRetriever interfaces. Version-lock CI. |
| Voyage-code-3 deprecation or pricing change | Low | Medium | LlamaIndex's embedding abstraction makes model swap a config change. |
| Framework becomes unmaintained | Very Low | High | 47.9K stars, commercial backing, MIT license. Migration target: Haystack (similar concepts, different API). |

---

## 8. What to Watch

1. **Agno retrieval depth.** Agno's RAG subsystem is growing fast. If it adds hierarchical indexing, query routing, and retrieval composition patterns, it could become a viable single-framework alternative (agent + retrieval). Worth re-evaluating in 6 months.
2. **Pydantic AI retrieval features.** The Pydantic team has acknowledged the gap (GitHub issue #58). If they build retrieval primitives with Pydantic-quality type safety, it could change the calculus.
3. **Haystack code-specific components.** If deepset or the community builds tree-sitter components, it could close the gap with LlamaIndex.
4. **Code-specific RAG frameworks.** Emerging projects like code-graph-rag (tree-sitter + knowledge graphs) may provide purpose-built alternatives. Monitor for production-readiness.
5. **Embedding model evolution.** If a model significantly outperforms Voyage-code-3 for code retrieval, the swap should be easy with LlamaIndex's abstraction.

---

## 9. Decision Summary

| Question | Answer |
|---|---|
| **Is LightRAG viable for Kenjutsu?** | No. Graph-RAG uses LLM entity extraction designed for prose, not code. |
| **Are modern agent frameworks (Agno, Pydantic AI, Strands) better than LlamaIndex for this?** | No. They solve a different problem (agent orchestration). Agno has the best RAG among them but lacks the retrieval composition patterns Kenjutsu needs. |
| **Is Mastra viable?** | No. TypeScript-only, incompatible with Kenjutsu's Python stack. |
| **Which framework should Kenjutsu use?** | LlamaIndex — deepest retrieval primitives, largest integration ecosystem, natural extension points for code-specific components. |
| **What is the runner-up?** | Haystack — architecturally clean, better debugging transparency, but requires more custom code. |
| **What about LangChain?** | Not as the retrieval foundation. Consider LangGraph as a complement for agentic search (Layer 3). |
| **How much custom code is needed?** | Four custom components (tree-sitter NodeParser, import graph retriever, co-change retriever, test file matcher). Seven retrieval capabilities are built-in. |
| **Primary risk?** | LlamaIndex API churn + abstraction debugging. Mitigated by version pinning and internal abstraction. |

---

## Sources

### RAG Orchestration Frameworks
- [LlamaIndex — GitHub](https://github.com/run-llama/llama_index) — 47,912 stars, MIT license
- [Haystack — GitHub (deepset)](https://github.com/deepset-ai/haystack) — 24,593 stars, Apache-2.0 license

### Agent Frameworks
- [Agno — GitHub](https://github.com/agno-agi/agno) — 38,900 stars, Apache-2.0 license
- [LangChain — GitHub](https://github.com/langchain-ai/langchain) — 130,768 stars, MIT license
- [Pydantic AI — GitHub](https://github.com/pydantic/pydantic-ai) — 15,700 stars, MIT license
- [Mastra — GitHub](https://github.com/mastra-ai/mastra) — 22,260 stars, Apache-2.0 license
- [AWS Strands Agents — GitHub](https://github.com/strands-agents/sdk-python) — 5,358 stars, Apache-2.0 license
- [Semantic Kernel — GitHub (Microsoft)](https://github.com/microsoft/semantic-kernel) — 27,531 stars, MIT license
- [DSPy — GitHub (Stanford NLP)](https://github.com/stanfordnlp/dspy) — 33,084 stars, MIT license

### Analysis and Comparisons
- [LangChain vs LlamaIndex (2026): Complete Production RAG Comparison](https://blog.premai.io/langchain-vs-llamaindex-2026-complete-production-rag-comparison/)
- [Production RAG in 2026: LangChain vs LlamaIndex](https://rahulkolekar.com/production-rag-in-2026-langchain-vs-llamaindex/)
- [The Best RAG Frameworks for Building Enterprise GenAI in 2026](https://www.tredence.com/blog/top-rag-frameworks)
- [15 Best Open-Source RAG Frameworks in 2026](https://www.firecrawl.dev/blog/best-open-source-rag-frameworks)
- [Custom RAG Pipeline for Context-Powered Code Reviews — Qodo](https://www.qodo.ai/blog/custom-rag-pipeline-for-context-powered-code-reviews/)
- [Agno Documentation — Hybrid Search](https://docs.agno.com/basics/knowledge/search-and-retrieval/hybrid-search)
- [Agno Changelog — AST-based Code Chunking](https://www.agno.com/changelog/higher-quality-code-retrieval-with-ast-based-chunking)
- [Pydantic AI Official Documentation](https://ai.pydantic.dev/)
- [Pydantic AI RAG Example](https://ai.pydantic.dev/examples/rag/)
- [Strands Agents Official Documentation](https://strandsagents.com/)
- [Introducing Strands Agents — AWS Blog](https://aws.amazon.com/blogs/opensource/introducing-strands-agents-an-open-source-ai-agents-sdk/)
- [Mastra RAG Documentation](https://mastra.ai/docs/rag/overview)
- [14 AI Agent Frameworks Compared (2025)](https://softcery.com/lab/top-14-ai-agent-frameworks-of-2025-a-founders-guide-to-building-smarter-systems)
- [Comparing AI Agent Frameworks — Atla AI](https://atla-ai.com/post/ai-agent-frameworks)

---

## Appendix A: LightRAG Architecture Detail

*Consolidated from the v1 evaluation for reference. The assessment above summarizes the conclusion; this appendix preserves the technical detail.*

### Indexing Phase

1. Documents are chunked (default 1200 tokens, 100-token overlap)
2. An LLM extracts entities and relationships from each chunk
3. Entities become graph nodes; relationships become edges
4. Each node and edge stores a structured textual profile
5. Chunks are embedded and stored in a vector database

### Query Phase — Six Retrieval Modes

| Mode | Behavior |
|---|---|
| **naive** | Vector-only similarity search (baseline) |
| **local** | Graph traversal for direct entity connections |
| **global** | Cross-document relationship discovery via graph |
| **hybrid** | Combined local + global |
| **mix** | Combines knowledge graph extraction with vector retrieval, applying both graph-based and semantic search strategies |
| **bypass** | Passes the query directly to the LLM without retrieval |

### Storage Backends (Pluggable)

- **KV:** JSON, PostgreSQL, Redis, MongoDB, OpenSearch
- **Vector:** NanoVectorDB, pgvector, Milvus, Chroma, Faiss, Qdrant, MongoDB, OpenSearch
- **Graph:** NetworkX, Neo4j, PostgreSQL (AGE), OpenSearch

### Cost Characteristics

- ~100 tokens per query vs. GraphRAG's ~610,000 (6,000x reduction enabled by skipping community clustering)
- Incremental updates via graph union (~50% faster update cycles vs. GraphRAG full rebuild)
- High indexing cost: LLM entity extraction required per chunk (32K+ context, 32B+ parameter model)

---

## Appendix B: Additional Systems Evaluated in v1

*These systems were evaluated in v1 but summarized in v3 Section 2 as "same fundamental mismatch." Full evaluations preserved here for reference.*

### Microsoft GraphRAG

| Attribute | Detail |
|---|---|
| **License** | MIT |
| **GitHub stars** | 31.7K |
| **Latest version** | v3.0.6 (March 2026) |
| **Maintainer** | Microsoft Research (not officially supported product) |

**Architecture:** Five-stage pipeline — document chunking → LLM entity/relationship extraction → Leiden algorithm community clustering → community summary report generation → dual-mode querying (local entity search + global community-based synthesis).

**Key differentiator:** Community detection and hierarchical summarization enable "global queries" that address themes across entire datasets ("what are the main security concerns in this codebase?").

**Cost:** Indexing is expensive — original benchmarks showed $33K for large datasets. LazyGraphRAG (2025) reduces indexing cost to 0.1% of full GraphRAG by deferring graph construction to query time.

**Fit for Kenjutsu: Poor.** Same fundamental mismatch as LightRAG (LLM entity extraction for code), compounded by prohibitive indexing costs and no incremental update support.

### R2R (RAG to Riches, SciPhi-AI)

| Attribute | Detail |
|---|---|
| **License** | MIT |
| **GitHub stars** | 7.7K |
| **Latest version** | v3.6.5 (June 2025) |
| **Maintainer** | SciPhi-AI |

**Architecture:** REST API-first system with three core pipelines — Ingestion (document parsing → embeddings), Embedding (vector storage), RAG (retrieval + LLM generation). Includes automatic knowledge graph extraction, hybrid search (semantic + keyword with RRF), and a Deep Research API for multi-step agentic reasoning.

**Strengths:** Production-oriented from day one (REST API, auth, observability); hybrid search with reciprocal rank fusion built-in; Python and JavaScript SDKs.

**Weaknesses:** Smaller community (7.7K stars, 70 contributors); no code-specific features; opinionated architecture harder to extend with custom indexing.

**Fit for Kenjutsu: Moderate.** R2R's hybrid search and production infrastructure are relevant, but it's a complete system rather than a composable toolkit. Integrating custom AST-based indexing would mean working against R2R's opinions rather than with them.

### Cognee (Topoteretes)

| Attribute | Detail |
|---|---|
| **License** | Apache-2.0 |
| **GitHub stars** | 14.5K |
| **Latest version** | v0.5.5 (March 2026) |
| **Maintainer** | Topoteretes |

**Architecture:** Memory-first knowledge engine combining vector search, graph databases, and cognitive science approaches. Modular pipeline: ingestion (30+ data sources) → enrichment (embeddings + graph "memify") → retrieval (graph traversal + vector similarity + time filtering).

**Strengths:** Memory-first design ideal for agentic systems; graph + vector hybrid unified architecture; multi-backend support (NetworkX for dev, Neo4j/FalkorDB for prod); tenant isolation and OTEL observability; Apache-2.0 license.

**Weaknesses:** Pre-v1.0 (v0.5.5) — API stability not guaranteed; incomplete documentation; no code-specific indexing or retrieval features.

**Fit for Kenjutsu: Moderate.** Cognee's incremental knowledge accumulation and agentic memory model are conceptually interesting for a code review tool that should learn from feedback over time. However, it's immature (pre-v1.0) and lacks code-specific features.

---

## Appendix C: Critical Finding — LLM Entity Extraction vs. AST Parsing for Code

*This standalone research synthesis was the core technical finding of the v1 evaluation. The main document references the conclusion in Section 2; the full analysis is preserved here.*

All graph-based RAG systems (LightRAG, GraphRAG, R2R, Cognee) use **LLM-based entity extraction**, designed for natural language documents. Recent research (Chinthareddy 2026, AST-derived DKB) demonstrates that for code retrieval:

1. **AST-derived graphs outperform LLM-extracted graphs** on code retrieval benchmarks (SWE-bench, RepoEval). Deterministic structural analysis captures function dependencies, call graphs, and type hierarchies that LLM extraction misses or hallucinates.

2. **AST parsing is free; LLM extraction is expensive.** Tree-sitter parses a file in milliseconds with zero API cost. LLM entity extraction costs tokens per chunk and takes seconds per call. For a codebase with thousands of files, the cost difference is orders of magnitude.

3. **Structural accuracy matters more than semantic richness for code.** When reviewing a PR, knowing that "function A calls function B which implements interface C" (AST-derived) is more useful than knowing "this module handles authentication" (LLM-extracted).

4. **Hybrid approaches win.** AST-grep for deterministic structure + natural language descriptions for semantic retrieval. The best code retrieval system combines cheap structural analysis (always) with selective semantic enrichment (when needed).

This finding is the primary reason none of the evaluated prebuilt graph-RAG systems are suitable as Kenjutsu's complete retrieval solution. They solve the wrong problem — document retrieval — while Kenjutsu needs code retrieval.

---

## Appendix D: Three-Layer Context Pipeline Architecture

*This architecture mapping from v1 shows how the LlamaIndex recommendation maps to the multi-layer context pipeline identified in prior research (DEM-108).*

```text
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

---

## Appendix E: Additional Sources (from v1)

- [LightRAG — EMNLP 2025 Paper](https://aclanthology.org/2025.findings-emnlp.568.pdf)
- [Microsoft GraphRAG — GitHub](https://github.com/microsoft/graphrag)
- [LazyGraphRAG — Microsoft Research](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/)
- [R2R — GitHub (SciPhi-AI)](https://github.com/SciPhi-AI/R2R)
- [Cognee — GitHub (Topoteretes)](https://github.com/topoteretes/cognee)
- [GraphRAG vs LightRAG Comparison](https://lilys.ai/en/notes/get-your-first-users-20260207/graphrag-lightrag-comparison)
- [GraphRAG vs LightRAG — Maarga Systems](https://www.maargasystems.com/2025/05/12/understanding-graphrag-vs-lightrag-a-comparative-analysis-for-enhanced-knowledge-retrieval/)
- [Reliable Graph-RAG for Codebases: AST-Derived (Chinthareddy 2026)](https://arxiv.org/pdf/2601.08773)
- [RAG Frameworks Comparison — Pathway](https://pathway.com/rag-frameworks)
- [Cognee — From RAG to Graphs (Memgraph)](https://memgraph.com/blog/from-rag-to-graphs-cognee-ai-memory)
- [cAST — Structural Chunking via AST (EMNLP 2025)](https://arxiv.org/html/2506.15655v1)
