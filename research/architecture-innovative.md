# Architecture Proposal: Innovative — Pushing the Envelope

**Date:** 2026-03-24 (v2 — revised per board feedback)
**Author:** Chief Architect
**Issue:** DEM-119
**Parent:** DEM-117

---

## Design Philosophy

This architecture proposes that the future of code review is not a better LLM prompt on a diff — it is a **system that deeply understands the entire codebase** through a persistent semantic graph, applies **specialized analysis through an agent constellation**, proves findings with **evidence-based confidence scoring**, and provides **governance for the age of AI-generated code.** Every component pushes beyond what current tools offer.

The innovative lens means:
- Ask "what would make competing approaches obsolete?" not "how do we match competitors?"
- Invest in structural advantages that compound over time
- Accept higher upfront cost for deeper long-term moats
- Build the system we wish existed, then figure out how to ship it incrementally

---

## Assumptions We Challenge

### 1. "A vector store is sufficient for code retrieval"

The research recommends Voyage-code-3 embeddings in a vector store with hybrid BM25 search (DEM-108) and LlamaIndex as the orchestration layer (DEM-114). This is correct for similarity search, but similarity search alone cannot answer structural questions that matter for code review: "What functions call this method?" "What services consume this API?" "Has this pattern been rejected before?" These require graph traversal, not vector similarity.

**Our position:** Build a Code Semantic Graph that combines structural relationships (AST-derived), semantic embeddings (vector), and temporal patterns (git history) in a unified knowledge graph. This is harder and more expensive than a vector store, but it enables capabilities that vector-only approaches cannot match: predictive analysis, cross-repo intelligence, and evidence-based confidence scoring.

### 2. "LlamaIndex is the right foundation"

DEM-114 makes a strong case for LlamaIndex as the retrieval framework. But LlamaIndex is designed for document retrieval — its abstractions (Documents, Nodes, Indexes, QueryEngines) model a document pipeline, not a code intelligence system. For this architecture's ambitions (persistent code graph, cross-repo traversal, predictive analysis), LlamaIndex would be an awkward fit. We'd spend more time working around its abstractions than leveraging them.

**Our position:** Build the Code Semantic Graph on a purpose-built graph database (SurrealDB embedded). Use LlamaIndex's concepts as inspiration (hierarchical indexing, hybrid retrieval, query routing) but implement them against our graph model. This is more custom code, but the result is a system designed for code intelligence rather than retrofitted from document retrieval.

**Risk acknowledged:** This is the highest-risk decision in this architecture. If the Code Semantic Graph proves too complex or too slow to maintain, falling back to LlamaIndex is the escape hatch. The retrieval interfaces should be designed so that swapping the CSG backend for LlamaIndex is possible without rewriting the review engine.

### 3. "Multi-agent adds latency without proportional value"

The balanced architecture (DEM-120) argues for evidence-gated multi-agent: start with one reviewer, add agents when data shows gaps. This is reasonable but conservative. The counter-argument: a single general-purpose reviewer with a single prompt tries to be an expert at everything and is an expert at nothing. Security analysis, performance analysis, and correctness checking require fundamentally different context retrieval strategies, different LLM configurations, and different prompt engineering. A security agent that retrieves data flow paths and credential patterns will catch vulnerabilities that a general agent misses entirely — not because the LLM is incapable, but because the relevant context was never retrieved.

**Our position:** Build multi-agent from the start, with the understanding that agent count is a dial, not a switch. MVP launches with 2-3 agents (Correctness + Security at minimum), not the full constellation. The Orchestrator and Meta-Agent exist from day one. This is more expensive per review but produces higher-quality, more differentiated output.

### 4. "The governance opportunity is speculative"

The pragmatic architecture defers governance to "when demand exists." We disagree. The EU AI Act (August 2026) and Colorado AI Act (June 2026) are not speculative — they are enacted legislation with implementation deadlines. Companies that need compliance will need it before August 2026, which means procurement decisions happen in early 2026. Governance is not a feature to add later — it is a market entry requirement for the enterprise segment.

**Our position:** Governance is first-class, not bolted on. AI provenance detection, risk-proportional review depth, compliance audit trails, and policy-as-code are built into the architecture from Phase 2. This is a bet on the regulatory timeline being real, and the downside of being wrong (unnecessary governance features that enterprise customers appreciate anyway) is mild compared to the downside of being late (losing the compliance window).

### 5. "Rust + Python is unnecessary complexity"

The pragmatic and balanced architectures choose all-Python for simplicity. This is correct for an MVP-focused architecture. But for a system that indexes entire codebases, maintains a persistent graph, and processes thousands of PRs per day, Python's performance limitations are real. Greptile's v3 struggled with memory management and workflow durability during indexing — these are problems that Rust eliminates structurally (memory safety, thread safety, zero-cost abstractions).

**Our position:** Use Rust for the performance-critical indexing pipeline and webhook server. Use Python for the intelligence layer (agents, prompts, LLM integration) where iteration speed matters more than raw performance. The boundary is clean: Rust handles data, Python handles intelligence. The cost is two-language complexity; the benefit is a system that can index million-line codebases without the operational problems that plagued Greptile.

**Risk acknowledged:** Two-language codebases increase hiring complexity and maintenance burden. If the team cannot staff Rust engineers, fall back to Python with careful attention to memory management and async patterns. The architecture should work with an all-Python implementation — Rust is an optimization, not a requirement.

---

## 1. Core Architecture: The Code Semantic Graph

### The Central Innovation

Every competitor starts with the diff and reaches outward for context. Kenjutsu inverts this: start with a **persistent, incrementally-maintained semantic graph of the entire codebase** and the diff is an event that queries into it.

The Code Semantic Graph (CSG) is not a vector store. It is a rich, typed knowledge graph that models:

- **Structural relationships** — function calls, type hierarchies, imports, module boundaries (tree-sitter AST, deterministic)
- **Semantic descriptions** — natural language summaries of every function/class (LLM-generated during indexing, 12% retrieval improvement over raw code per Greptile data)
- **Temporal evolution** — who changed what, when, why (git history, commit messages, PR metadata)
- **Cross-repository dependencies** — API contracts, shared types, service boundaries
- **Review decisions** — past findings, accepted/rejected suggestions, team patterns
- **Test coverage mapping** — which functions have tests, which don't

### Why a Graph, Not Just Vectors

Vector stores answer: "find chunks similar to this query." They cannot answer:

- "What functions call this method I just changed?"
- "What other services consume this API endpoint?"
- "Has this pattern been flagged before, and what did the team decide?"
- "What tests need updating given this change?"

A graph answers these through traversal. The CSG combines **graph traversal for structural queries + vector similarity for semantic queries.** This is the architecture that makes predictive analysis and cross-repo intelligence possible.

**Graph technology: SurrealDB (embedded mode).** Graph + document + vector in one engine, Rust core, embeddable (single binary deployment), SQL-like query language. The embedded mode means no external service dependency — critical for self-hosted enterprise.

**Fallback acknowledged:** If SurrealDB proves unstable, PostgreSQL (pgvector + recursive CTEs for graph traversal) is the migration target. We lose the single-binary story but keep the architecture. The CSG schema is defined as a logical model, not coupled to the storage engine.

### Indexing Pipeline

```
Repository Clone/Fetch
       │
       ▼
┌──────────────────┐
│ AST Parser        │  tree-sitter (universal, incremental)
│                   │  Extract: functions, classes, imports, types, call sites
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Semantic Enricher │  LLM generates NL descriptions per function/class
│                   │  Content-hash keyed — unchanged code reuses cached descriptions
│                   │  Haiku-class model for cost efficiency
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Embedding Engine  │  Voyage-code-3 @ 1024 dims (Matryoshka)
│                   │  Embeds NL descriptions (primary) + raw code (fallback)
│                   │  Binary quantization for storage efficiency
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Graph Builder     │  Constructs/updates CSG nodes and edges
│                   │  Structural edges from AST (calls, imports, inheritance)
│                   │  Temporal edges from git history (co-change, authorship)
│                   │  Cross-repo edges from API contract analysis
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Code Semantic     │  Persistent, incrementally maintained
│ Graph (CSG)       │  SurrealDB embedded (graph + vector + document)
│                   │  Merkle-tree change detection for incremental updates
└──────────────────┘
```

**Incremental updates:** Content-hash each chunk. Re-index only changed files on every PR/push. Merkle-tree directory hashing for fast change detection. Target: incremental update in < 30 seconds for typical PRs.

---

## 2. Review Architecture: Agent Constellation

### Beyond Single-Pass Review

Every competitor runs review in a single process (even Qodo 2.0's "multi-agent"). Kenjutsu uses Paperclip's orchestration to run a **constellation of specialized agents**, each with its own context retrieval strategy, prompt engineering, and LLM configuration.

```
PR Event
   │
   ▼
┌─────────────────┐
│ Orchestrator     │  Analyzes diff → selects agents → dispatches in parallel
└──────┬──────────┘
       │
       ├──────────────────┐──────────────────┐
       ▼                  ▼                  ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ Correctness │   │ Security    │   │ Architecture│
│ Agent       │   │ Agent       │   │ Agent       │
│             │   │             │   │             │
│ Logic bugs  │   │ Taint paths │   │ Dependency  │
│ Edge cases  │   │ OWASP       │   │ violations  │
│ Type safety │   │ Credentials │   │ API breaks  │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                  │                  │
       └──────────┬───────┘──────────────────┘
                  ▼
        ┌─────────────────┐
        │ Meta-Agent      │  Deduplicate, rank, resolve conflicts
        │                 │  Apply team calibration
        │                 │  Enforce confidence thresholds
        │                 │  Produce coherent review
        └─────────────────┘
```

### Agent Specialization

Each agent in the constellation:

1. **Retrieves different context from the CSG.** Security Agent: data flow paths, external inputs, credential patterns. Architecture Agent: dependency graph, module boundaries, API contracts. Correctness Agent: type hierarchies, similar implementations, test coverage.

2. **Uses different LLM configurations.** Security: extended thinking (Opus-class). Architecture: broad context (200K window). Correctness: fast, cheaper models (Sonnet-class).

3. **Has specialized prompts.** Domain-tuned with domain-specific patterns, rules, and examples.

4. **Produces typed, structured findings** with severity, confidence, evidence chain, and suggested fix.

5. **Learns independently** from team feedback (accepted/rejected/ignored findings).

### The Meta-Agent

The Meta-Agent is the quality gate:
- **Deduplicates** across agents (Security and Correctness may both flag a null pointer)
- **Resolves conflicts** (Performance says "inline this," Architecture says "keep the abstraction" — Meta-Agent weighs evidence)
- **Applies team calibration** — noise tolerance adjusts per team based on feedback history
- **Ranks by severity and confidence** — critical high-confidence findings float to top
- **Produces coherent narrative** — reads like one expert, not a committee

---

## 3. Predictive Analysis Engine

### Beyond Reactive Review

Current tools answer: "Is there a problem with what you changed?" Kenjutsu also answers: **"What did you forget to change?"**

**Co-change prediction:** CSG temporal layer tracks files that historically change together. When PR modifies A but not B, and co-change probability > 80%: "File B usually changes with A — was this intentional?"

**Missing test detection:** CSG maps test coverage at function level. New functions without tests flagged with specific test file location and suggested test skeleton.

**Stale documentation detection:** When a function's behavior changes, CSG checks if linked documentation was also updated.

**Cross-repo impact analysis:** When a shared API changes, CSG identifies all consumers across repos and flags affected locations.

**Pattern regression detection:** CSG tracks patterns rejected in previous reviews. If a PR reintroduces a rejected pattern, proactively flags with links to past decisions.

**Implementation:** Most predictions are **deterministic** (graph traversal, statistical analysis) — no LLM calls needed. The LLM generates human-readable explanations and assesses relevance given the PR's stated intent. Fast and cheap.

---

## 4. Evidence-Based Confidence System

### Confidence Taxonomy

Every finding carries a confidence classification based on evidence source:

| Tier | Evidence Source | Expected FP Rate | Example |
|---|---|---|---|
| **Verified** | AST-grep pattern match, type system violation | < 1% | Hardcoded credentials, SQL injection pattern |
| **Graph-Derived** | CSG traversal (dependency violation, API break) | < 5% | "Function callers expect return value you removed" |
| **LLM-High** | LLM finding confirmed by graph evidence | < 10% | Logic error backed by type/flow analysis |
| **LLM-Medium** | LLM finding, self-reflection score >= 7/10, no graph confirmation | 10-20% | Potential edge case, code smell |
| **LLM-Low** | Self-reflection score < 7/10 | > 20% | Style suggestions, subjective opinions |

**Default filter:** Only show Verified, Graph-Derived, and LLM-High. Target blended FP rate under 5% out of the box. Teams adjust threshold up or down.

**Key insight:** Deterministic analysis (AST-grep, graph traversal) produces highest-confidence findings at lowest cost. The LLM explains, contextualizes, and catches what deterministic analysis misses — it is not the primary detection mechanism.

---

## 5. Governance Engine

### First-Class, Not Bolted On

**AI code provenance detection:** Analyze PRs for AI-generation signals (tool-specific patterns, statistical analysis, explicit metadata). Classify changes as: human-authored, AI-assisted, or AI-generated.

**Risk-proportional review depth:** Risk score based on file sensitivity, change magnitude, author history, AI generation signals, blast radius. Higher risk → more agents, deeper context, stricter thresholds, human escalation.

**Compliance audit trail:** Every review produces a structured, immutable, queryable record: which agents reviewed, what findings generated, what team decided, who approved merge, under what policy.

**Policy-as-code:** `.kenjutsu/governance.toml`:

```toml
[policies.security-critical]
paths = ["src/auth/**", "src/payment/**"]
required_agents = ["security", "correctness"]
min_confidence = "graph-derived"
require_human_approval = true

[policies.generated-code]
ai_generated_threshold = 0.8
additional_agents = ["correctness", "security"]
require_human_review = true
```

---

## 6. Data Flow

### End-to-End Review

```
T+0s     GitHub webhook → HMAC verify → debounce → enqueue
T+1s     Diff processor: fetch → parse → tree-sitter extension → chunk
T+2s     CSG query: incremental update (changed files) + per-agent context retrieval
T+3s     Governance: risk scoring → agent selection → policy evaluation
T+3s     Orchestrator: parallel dispatch to 2-3 agents via Paperclip
T+3-25s  Each agent: specialized context + prompt + LLM call + self-reflection
T+25s    CSG verification: confirm findings against graph evidence
T+30s    Meta-Agent: aggregate → deduplicate → rank → calibrate → narrative
T+35s    Publisher: pending review → atomic submit + Check Run + audit record
```

**Latency:** 35-60 seconds for standard PR (parallel agent execution). Deterministic analysis < 5 seconds. LLM calls are the long pole at 15-25 seconds each.

**Cost:** Sonnet-class for most agents, Opus-class for Security deep analysis and Meta-Agent conflict resolution. Estimated $0.30-0.60 per standard PR, $1.50-3.00 per large PR. Prompt caching reduces input costs up to 90%.

---

## 7. Technology Choices

### Language: Rust Core + Python Intelligence

**Rust** for performance-critical path: CSG indexing, diff processing, webhook server (Axum), graph construction. Compiles to single binary for self-hosted deployment.

**Python** for intelligence layer: LLM integration (Anthropic SDK, LiteLLM), prompt engineering (Jinja2, Pydantic), Paperclip agent runtime.

**Boundary:** Rust handles data; Python handles intelligence. FFI via PyO3.

**Fallback:** If Rust staffing is untenable, all-Python with careful memory management. Architecture works either way — Rust is an optimization.

### Key Dependencies

| Component | Technology | Rationale |
|---|---|---|
| Webhook server | Axum (Rust) | Async, high-throughput, zero-copy |
| AST parsing | tree-sitter (Rust bindings) | Universal, incremental, production-proven |
| Pattern matching | ast-grep (Rust) | YAML-defined patterns over ASTs |
| Graph database | SurrealDB (embedded) | Graph + vector + document, single binary |
| Embeddings | Voyage-code-3 @ 1024d | SOTA code retrieval, Matryoshka dims |
| LLM (primary) | Claude Sonnet 4.5 | Best cost/quality, 200K context |
| LLM (deep) | Claude Opus 4.6 | Extended thinking for security, conflicts |
| LLM (indexing) | Claude Haiku 4.5 | Fast, cheap NL descriptions |
| Agent orchestration | Paperclip | Multi-agent, governance, provenance |
| Task queue | NATS JetStream | Lightweight, embeddable, persistent |

### What We Avoid

- **LlamaIndex as foundation** — its document-retrieval abstractions would constrain the CSG design. (Study its patterns; don't adopt its framework.)
- **Graph-RAG systems** (LightRAG, GraphRAG) — per DEM-114, LLM entity extraction is wrong for code. AST parsing is deterministic, free, and more accurate.
- **Dynaconf / global state** — explicit configuration injection via Pydantic.
- **Monolithic dependencies** — optional extras: `kenjutsu[github]`, `kenjutsu[embeddings]`.

---

## 8. Cross-Repository Intelligence

### The Unoccupied Gap

No competitor does multi-repo well. Greptile explicitly struggles. CodeRabbit doesn't attempt it. This is Kenjutsu's most aggressive differentiation vector.

**Organization-level CSG** spanning all repositories with cross-repo edges:
- **API contract edges:** OpenAPI, GraphQL, gRPC specs linked to consumers
- **Shared library edges:** Package dependencies with version constraints
- **Data schema edges:** Database schemas, event schemas (Avro, Protobuf) linked to readers/writers
- **Deploy dependency edges:** Service graphs from docker-compose, Kubernetes manifests

**Example scenario:** Service A changes a REST endpoint schema. CSG identifies services B, C, D as consumers. Architecture Agent flags with specific file/line locations across repos.

---

## 9. Trade-offs and Rationale

| Decision | What We Gain | What We Risk | Mitigation |
|---|---|---|---|
| Code Semantic Graph (vs vector store) | Structural queries, predictions, cross-repo | Complex to build, significant infra | Start single-repo; CSG works with partial graph |
| Rust + Python (vs all-Python) | Performance for indexing, single-binary deploy | Two-language complexity, hiring | Clean boundary; fall back to all-Python if needed |
| Multi-agent from start (vs single agent) | Specialized, parallel, higher quality | Higher per-review cost, orchestration complexity | Agent count is a dial; simple PRs get fewer agents |
| SurrealDB (vs PostgreSQL) | Unified store, simple deployment | Younger project, less battle-tested | Schema is portable; PostgreSQL + pgvector is fallback |
| Governance first-class (vs deferred) | Enterprise market, regulatory compliance | Investment in uncertain demand | Downside of unnecessary governance features is mild |
| Cross-repo intelligence | Unique differentiator, enterprise value | Org-level access, indexing cost | Gate behind enterprise tier; start with config-driven |
| No LlamaIndex (vs framework adoption) | Custom-fit for code intelligence | More custom code to maintain | Study LlamaIndex patterns; LlamaIndex is escape hatch |

---

## 10. Phased Delivery

### Phase 0: Foundation (Weeks 1-6)

- Rust webhook server (Axum) + HMAC verification
- GitHub App registration and token management
- Diff processor (tree-sitter hunk extension, token-aware chunking)
- Correctness Agent + Security Agent (Python, via Paperclip)
- Meta-Agent for aggregation
- Publisher (pending review, Check Runs)

**Exit criteria:** Reviews real PRs with 2 agents, heuristic context only.

### Phase 1: Code Semantic Graph (Weeks 7-14)

- tree-sitter AST extraction pipeline (Rust)
- NL description generation (Haiku batch processing)
- Voyage-code-3 embedding pipeline with content-hash caching
- SurrealDB graph construction (structural + temporal edges)
- Graph-enhanced context retrieval for all agents

**Exit criteria:** Multi-agent review with full single-repo codebase context via CSG.

### Phase 2: Governance + Confidence (Weeks 15-20)

- Governance Engine (risk scoring, AI provenance, policy-as-code)
- Evidence-based confidence system (Verified → Graph-Derived → LLM tiers)
- Predictive Analysis Engine (co-change, missing tests, stale docs)
- Feedback learning (per-agent, per-team calibration)
- Audit trail and compliance reporting

**Exit criteria:** Governance-aware, evidence-graded, learning review system.

### Phase 3: Cross-Repo + Distribution (Weeks 21-28)

- Organization-level CSG spanning multiple repos
- API contract analysis (OpenAPI, GraphQL, gRPC)
- Cross-repo impact detection
- Architecture Agent with dependency graph queries
- GitHub Action distribution
- Governance dashboard

**Exit criteria:** Multi-repo intelligence. Three distribution channels (App, Action, self-hosted binary).

---

## 11. Infrastructure and Cost Projections

### Phase 0 Infrastructure

| Component | Monthly Cost |
|---|---|
| Webhook server (Axum container) | $20-50 |
| Task queue (NATS JetStream) | $15-30 |
| Monitoring | $0-30 |
| **Total** | **$35-110** |

### Phase 1+ Infrastructure (with CSG)

| Component | Monthly Cost |
|---|---|
| SurrealDB storage | $0-50 (embedded) |
| Embedding service (Voyage AI) | $0.06-0.12/1M tokens |
| Background workers (indexing) | $30-100 |
| Storage (embeddings + graph) | $10-50 |
| **Total additions** | **$40-200** |

### LLM Cost per Review (Multi-Agent)

| PR Size | Agents | Cost (no caching) | Cost (with caching) |
|---|---|---|---|
| Small (1-5 files) | 2 | $0.25 | $0.10 |
| Typical (5-15 files) | 2-3 | $0.50 | $0.20 |
| Large (15-50 files) | 3 | $2.00 | $0.75 |

Higher per-review cost than single-agent, but the quality delta justifies it for teams that value review depth.

---

## 12. Risk Assessment

### Risks We Accept

| Risk | Likelihood | Impact | Acceptance Rationale |
|---|---|---|---|
| CSG indexing too slow for large codebases | Medium | Medium | Incremental updates are fast; initial index runs in background |
| Multi-agent cost is higher than single-agent | High | Low | Cost is a dial (agent count adjustable); quality is the priority |
| SurrealDB stability | Medium | Medium | Schema is portable; PostgreSQL fallback exists |
| Two-language complexity | Medium | Medium | Clean boundary; Python-only fallback if needed |

### Risks We Mitigate

| Risk | Mitigation |
|---|---|
| CSG doesn't scale | Merkle-tree change detection; pre-compute common queries as materialized views |
| Rust velocity too slow | Rust scope is bounded (indexing + webhook); intelligence layer is all Python |
| Multi-agent orchestration complexity | Paperclip handles coordination; agent count starts at 2, not full constellation |
| FP rate with multi-agent | Evidence-based confidence system; Meta-Agent quality gate |
| Graph queries too slow for real-time | Pre-computed views, query timeouts, fallback to vector-only |

### Risks We Avoid

| Risk | How |
|---|---|
| AGPL contamination | Build from scratch |
| Graph-RAG systems (LLM entity extraction for code) | AST parsing (deterministic, free, correct) |
| Vendor lock-in | SurrealDB embedded, LiteLLM for LLMs, provider abstraction for git |

---

## 13. What Makes This "Innovative"

This architecture earns the "innovative" label through five structural bets that no competitor makes:

1. **The Code Semantic Graph.** A persistent, incrementally-maintained knowledge graph that combines structural relationships (AST), semantic understanding (embeddings), and temporal evolution (git history). This is not a vector store with extra steps — it is a fundamentally different approach to codebase intelligence that enables capabilities (predictive analysis, cross-repo impact, evidence-based confidence) that are structurally impossible with similarity search alone.

2. **Agent Constellation.** Not "run multiple prompts" — a true distributed multi-agent system where each agent retrieves different context, uses different LLM configurations, has specialized prompts, and learns independently. The Meta-Agent produces a coherent review from diverse expert opinions. This is possible only because Paperclip provides the orchestration infrastructure.

3. **Evidence-Based Confidence.** Every finding is classified by evidence strength (Verified > Graph-Derived > LLM). Deterministic analysis produces the highest-confidence findings at the lowest cost. The LLM is the explainer and gap-filler, not the primary detection mechanism. This inverts the architecture of every competitor (where the LLM is the detection mechanism and everything else is context).

4. **Predictive Analysis.** Answering "what did you forget to change?" not just "is what you changed correct?" Co-change prediction, missing tests, stale docs, pattern regression — mostly deterministic, mostly free, and something no competitor offers.

5. **Cross-Repository Intelligence.** The CSG spans the entire organization. API contracts, shared libraries, data schemas, and deploy dependencies create cross-repo edges. When a service changes its API, Kenjutsu knows every consumer. This is the gap that every single-repo tool cannot fill without fundamental architectural change.

The risk is proportional to the ambition: this is harder to build than a single-agent diff reviewer. The timeline is longer (28 weeks to full capability vs 12-16 for pragmatic). But if built, it creates a product that competitors cannot replicate by tuning their prompts — because the moat is structural, not algorithmic.

---

## Sources

This architecture synthesizes findings from:
- Competitive analysis (DEM-105): Market positioning, feature gaps, context depth benchmarks
- PR-Agent deep-dive (DEM-106): Architecture patterns, diff processing, AGPL finding
- GitHub integration (DEM-107): App vs Action, rate limits, API patterns
- Context/RAG strategies (DEM-108): Embedding approaches, AST parsing, hybrid retrieval, the case for NL descriptions
- Differentiation (DEM-109): Market gaps, governance opportunity, multi-agent positioning
- Technical feasibility (DEM-110): Build vs fork, timeline, cost projections
- Retrieval framework evaluation (DEM-114): LlamaIndex assessment (adopted as inspiration, not framework), graph-RAG category mismatch (validates AST over LLM entity extraction), Agno code chunking reference
