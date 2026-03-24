# Architecture Proposal: Innovative — Pushing the Envelope

**Date:** 2026-03-23
**Author:** Chief Architect
**Issue:** DEM-119
**Parent:** DEM-117

---

## Thesis

The AI code review market is converging on a commodity: every tool runs an LLM on a diff and posts comments. The winners in this market will not be incrementally better diff-reviewers — they will be the ones who redefine what code review means. This architecture proposes Kenjutsu as **the first code review system built around a persistent semantic understanding of the entire codebase**, powered by **specialized multi-agent review constellations**, with **governance and provenance as first-class architectural concerns**. The goal is not to compete with CodeRabbit and Greptile on their terms — it is to make their approach obsolete.

---

## 1. Core Architecture: The Code Semantic Graph

### The Central Innovation

Every competitor starts with the diff and reaches outward for context. Kenjutsu inverts this: we start with a **persistent, incrementally-maintained semantic graph of the entire codebase** and the diff is an event that queries into it.

The Code Semantic Graph (CSG) is not a vector store. It is a rich, typed knowledge graph that models:

- **Structural relationships** — function calls, type hierarchies, imports, module boundaries (extracted via tree-sitter AST parsing)
- **Semantic descriptions** — natural language summaries of every function, class, and module (LLM-generated during indexing, following Greptile's validated approach: 12% retrieval improvement over raw code embeddings)
- **Temporal evolution** — who changed what, when, why (mined from git history, commit messages, and PR metadata)
- **Cross-repository dependencies** — API contracts, shared types, service boundaries (the gap every competitor ignores)
- **Review decisions** — past findings, accepted/rejected suggestions, team-specific patterns (the learning layer)
- **Test coverage mapping** — which code paths have tests, which don't, which tests exercise which functions

The CSG is the intelligence layer that makes everything else possible. It is what transforms Kenjutsu from "an LLM that reads diffs" into "a system that understands your codebase."

### Why a Graph, Not a Vector Store

Vector stores (LanceDB, ChromaDB, Qdrant) are good at one thing: "find chunks similar to this query." They are blind to structure. They cannot answer:

- "What functions call this method I just changed?"
- "What other services consume this API endpoint?"
- "Has this pattern been flagged before, and what did the team decide?"
- "What tests need to be updated given this change?"

A graph answers all of these through traversal, not similarity search. The CSG combines both: **graph traversal for structural queries, vector similarity for semantic queries, and the intersection for context retrieval that is both precise and relevant.**

### Graph Technology Choice

**SurrealDB** (embedded mode) or **TypeDB** (formerly Grakn).

SurrealDB offers: embedded deployment (no external service), graph + document + vector in one engine, SQL-like query language, Rust core (performance), WASM compilation target. The embedded mode means Kenjutsu can run as a single binary with the graph built-in — critical for self-hosted enterprise deployment.

TypeDB offers: a type system for the graph (enforces schema on relationships), built-in reasoning engine (infer transitive dependencies), designed for knowledge graphs. Higher learning curve but stronger modeling guarantees.

**Bet:** SurrealDB for MVP (simpler, embedded, multi-model), with the option to migrate to TypeDB if the reasoning engine proves necessary for cross-repo dependency analysis.

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
│ Semantic Enricher │  LLM generates natural language descriptions
│                   │  per function/class (batch, async, cached)
│                   │  Content-hash keyed — unchanged code reuses cached descriptions
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Embedding Engine  │  Voyage-code-3 @ 1024 dims (Matryoshka)
│                   │  Embeds natural language descriptions, not raw code
│                   │  Binary quantization for storage efficiency (32x reduction)
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
│ Graph (CSG)       │  Graph + vector + document in one engine
│                   │  Merkle-tree change detection (Cursor's approach)
└──────────────────┘
```

**Incremental updates:** On every PR or push, only re-index changed files. Content-hash each chunk — if the hash matches, skip re-embedding and re-describing. Merkle-tree structure at the directory level for fast change detection. Target: incremental index update in < 30 seconds for typical PRs.

**Cross-repo indexing:** For organizations with multiple repositories, the CSG spans all of them. API endpoints in service A are linked to consumers in service B. Type definitions in a shared library are linked to every usage across the org. This is the multi-repo intelligence gap that no competitor fills.

---

## 2. Review Architecture: Agent Constellation

### Beyond Single-Pass Review

Every competitor (even Qodo 2.0's "multi-agent" system) runs review logic in a single process. Kenjutsu uses Paperclip's multi-agent orchestration to run a **constellation of specialized review agents**, each with its own context retrieval strategy, prompt engineering, and LLM configuration.

### The Constellation

```
PR Event
   │
   ▼
┌─────────────────┐
│ Orchestrator     │  Paperclip-native coordinator
│                  │  Analyzes diff → decides which agents to invoke
│                  │  Routes based on: file types, change patterns, risk signals
└──────┬──────────┘
       │ Parallel dispatch via Paperclip
       ├──────────────────────────────────────────────┐
       │                    │                          │
       ▼                    ▼                          ▼
┌─────────────┐   ┌─────────────┐            ┌─────────────┐
│ Security    │   │ Architecture│            │ Correctness │
│ Agent       │   │ Agent       │            │ Agent       │
│             │   │             │            │             │
│ Taint       │   │ Dependency  │            │ Logic bugs  │
│ analysis,   │   │ violations, │            │ Edge cases  │
│ OWASP,      │   │ pattern     │    ...     │ Type errors │
│ secrets,    │   │ drift,      │            │ Null safety │
│ injection   │   │ API breaks  │            │ Race conds  │
└──────┬──────┘   └──────┬──────┘            └──────┬──────┘
       │                  │                          │
       └──────────────────┼──────────────────────────┘
                          │
                          ▼
                ┌─────────────────┐
                │ Meta-Agent      │  Aggregates, deduplicates, ranks
                │                 │  Resolves disagreements
                │                 │  Applies team calibration
                │                 │  Enforces confidence threshold
                │                 │  Produces final review
                └─────────────────┘
```

### Agent Specialization

Each agent in the constellation:

1. **Retrieves different context from the CSG.** The Security Agent queries for data flow paths, external inputs, and credential patterns. The Architecture Agent queries for dependency graphs, module boundaries, and API contracts. The Correctness Agent queries for type hierarchies, similar implementations, and test coverage.

2. **Uses different LLM configurations.** Security analysis benefits from extended thinking (Claude Opus with thinking tokens). Architecture review needs broad context (200K window). Correctness checks can use faster, cheaper models (Sonnet-class) for throughput.

3. **Has specialized prompt engineering.** Each agent's prompts are tuned for its domain. The Security Agent's prompts include OWASP patterns, common vulnerability signatures, and taint tracking instructions. The Architecture Agent's prompts include dependency rules, module boundary enforcement, and API contract validation.

4. **Produces typed, structured findings.** Every finding includes: severity, confidence score, evidence chain, affected code locations, and suggested fix. This structured output enables the Meta-Agent to aggregate intelligently.

5. **Learns independently.** When a team accepts or rejects a finding from a specific agent, that signal feeds back into that agent's calibration — adjusting thresholds, updating team-specific rules, refining prompt templates.

### The Meta-Agent

The Meta-Agent is the quality gate. It:

- **Deduplicates** findings across agents (the Security Agent and Correctness Agent may both flag a null pointer — only one finding should appear)
- **Resolves conflicts** (if the Performance Agent says "inline this function" and the Architecture Agent says "keep the abstraction," the Meta-Agent weighs the evidence)
- **Applies team calibration** — each team has a noise tolerance. New teams start with aggressive filtering (high confidence threshold). As the team provides feedback, the threshold adjusts.
- **Ranks by severity and confidence** — critical findings with high confidence float to the top. Low-confidence style suggestions are suppressed entirely by default.
- **Produces the final review** — a single, coherent PR review that reads like it came from one expert reviewer, not a committee.

### Why Paperclip Makes This Possible

This constellation architecture is not just "run multiple prompts." It requires:

- **Parallel execution with budget tracking** — Paperclip manages agent budgets, preventing unbounded LLM costs
- **Agent identity and provenance** — every finding is attributable to a specific agent, creating an audit trail
- **Escalation and governance** — the chain of command resolves disputes; humans can override any agent
- **Composability** — teams configure which agents review which directories/file types. A data pipeline team might disable the UI Agent and enable a Data Quality Agent.

No competitor has this infrastructure. Qodo 2.0's "multi-agent" runs in a single process. CodeRabbit's multi-stage pipeline is a fixed sequence. Kenjutsu's constellation is a true distributed multi-agent system with governance.

---

## 3. Predictive Analysis Engine

### Beyond Reactive Review

Current tools answer: "Is there a problem with what you changed?" Kenjutsu also answers: **"What did you forget to change?"**

### Predictive Capabilities

**Co-change prediction:** The CSG's temporal layer tracks which files historically change together. When a PR modifies file A but not file B, and the co-change probability is > 80%, Kenjutsu flags: "File B usually changes with file A — was this intentional?"

**Missing test detection:** The CSG maps test coverage at the function level. New functions without corresponding tests are flagged with the specific test file where the test should live and a suggested test skeleton.

**Stale documentation detection:** When a function's signature or behavior changes, the CSG checks if linked documentation (docstrings, README sections, API docs) was also updated. If not, it flags the stale docs with the specific location.

**Cross-repo impact analysis:** When a shared library's API changes, the CSG identifies all consuming services and flags: "This API change affects 3 consumers: service-X (line 42), service-Y (line 108), service-Z (line 77). None of these repos are included in this PR."

**Pattern regression detection:** The CSG tracks patterns that the team has historically flagged. If a PR introduces a pattern that was rejected in 3+ previous reviews, it proactively flags: "This pattern was rejected in PRs #142, #187, #203 — consider the alternative used in those PRs."

### Implementation

The Predictive Analysis Engine is a specialized agent in the constellation. It queries the CSG's temporal and structural layers rather than performing LLM-based analysis. Most predictions are **deterministic** (graph traversal, statistical co-change analysis) — they don't require LLM calls, making them fast and cheap.

The LLM is only invoked to generate human-readable explanations of the predictions and to assess whether the prediction is relevant given the PR's stated intent (extracted from the PR description and commit messages).

---

## 4. Evidence-Based Confidence System

### The Precision Imperative

False positives are the #1 adoption killer (research consensus). Kenjutsu's architecture addresses this at the structural level, not just through prompt engineering.

### Confidence Taxonomy

Every finding carries a confidence classification based on its evidence source:

| Confidence Tier | Evidence Source | Expected FP Rate | Example |
|---|---|---|---|
| **Verified** | AST-grep pattern match, type system violation, deterministic analysis | < 1% | Hardcoded credentials, SQL injection pattern, unused import |
| **Graph-Derived** | CSG traversal (dependency violation, API contract break, missing co-change) | < 5% | "This function's callers expect a return value you removed" |
| **LLM-High** | LLM finding confirmed by self-reflection pass AND graph evidence | < 10% | Logic error where the LLM's reasoning is backed by type/flow analysis |
| **LLM-Medium** | LLM finding with self-reflection score >= 7/10, no graph confirmation | 10-20% | Potential edge case, code smell |
| **LLM-Low** | LLM finding with self-reflection score < 7/10 | > 20% | Style suggestions, subjective opinions |

### Filtering Strategy

By default, Kenjutsu only surfaces **Verified**, **Graph-Derived**, and **LLM-High** findings. This targets a blended FP rate under 5% out of the box. Teams can adjust the threshold — lowering it to see more findings (accepting higher noise) or raising it for critical-path code.

The key insight: **deterministic analysis (AST-grep, graph traversal) produces the highest-confidence findings at the lowest cost.** LLM analysis is the most expensive and least reliable signal. The architecture prioritizes deterministic evidence and uses the LLM to explain, contextualize, and catch what deterministic analysis misses — not as the primary detection mechanism.

### Self-Reflection with Evidence

PR-Agent's self-reflection pass (second LLM call scoring each finding 0-10) is good but insufficient. Kenjutsu extends this:

1. **Generate finding** (agent LLM call)
2. **Verify against CSG** — can the finding be confirmed by graph traversal or AST analysis?
3. **Self-reflect** — a second LLM call evaluates the finding given the verification results
4. **Classify confidence** — based on the verification + self-reflection combined score
5. **Apply team calibration** — adjust threshold based on historical accept/reject rates for this finding type

---

## 5. Governance Engine

### First-Class, Not Bolted On

Governance in Kenjutsu is not an enterprise add-on. It is a core architectural layer that influences how every review is conducted, recorded, and audited.

### Capabilities

**AI code provenance detection.** Analyze PRs for signals of AI-generated code: tool-specific patterns (Copilot's comment style, Cursor's edit markers), statistical analysis (entropy, naming patterns, comment density), and explicit metadata (GitHub Copilot headers, Claude Code attribution). Classify each change as: human-authored, AI-assisted, or AI-generated.

**Risk-proportional review depth.** Not all code deserves the same review intensity. The Governance Engine assigns a risk score based on:
- File sensitivity (authentication, payment, data access layers = high risk)
- Change magnitude (large refactors vs single-line fixes)
- Author history (new contributor vs established maintainer)
- AI generation signals (AI-generated code gets deeper review)
- Blast radius (changes to shared libraries vs leaf modules)

Higher risk triggers: more agents in the constellation, deeper context retrieval, stricter confidence thresholds, and escalation to human reviewers.

**Compliance audit trail.** Every review produces a structured audit record:
- Which agents reviewed, with what context
- What findings were generated, at what confidence
- What the team decided (accepted, rejected, deferred)
- Who approved the merge, under what policy
- Time-stamped, immutable, queryable

This directly addresses EU AI Act (August 2026) and Colorado AI Act (June 2026) requirements for AI system documentation and human oversight of high-risk AI.

**Policy-as-code.** Teams define review policies in a `.kenjutsu/governance.toml` file:

```toml
[policies.security-critical]
paths = ["src/auth/**", "src/payment/**", "src/crypto/**"]
required_agents = ["security", "correctness"]
min_confidence_threshold = "graph-derived"
require_human_approval = true
escalation_contact = "security-team"

[policies.generated-code]
ai_generated_threshold = 0.8
additional_agents = ["correctness", "security"]
require_human_review = true
label = "ai-generated"
```

### Provenance in the Audit Trail

Every finding in Kenjutsu is attributable to a specific agent. The Paperclip agent identity system means:
- Security findings come from the Security Agent (with agent ID, model used, prompt version)
- Architecture findings come from the Architecture Agent
- The Meta-Agent's aggregation decisions are also recorded

This is not just logging — it enables: "Show me all security findings from the last quarter where the team overrode the agent" or "What is the false positive rate of the Architecture Agent for this team?"

---

## 6. Data Flow: End-to-End Review

```
GitHub Webhook (PR opened/synchronized)
       │
       ▼
┌──────────────────┐
│ Event Gateway     │  HMAC-SHA256 verification
│                   │  Debounce (30s window for rapid pushes)
│                   │  Enqueue to task queue
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Diff Processor    │  Fetch diff via GitHub API
│                   │  Parse into structured patches
│                   │  Extend hunks to enclosing functions (tree-sitter)
│                   │  Token-aware chunking
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ CSG Query Engine  │  Incremental graph update (changed files only)
│                   │  Per-agent context retrieval:
│                   │    Security: data flow paths, external inputs
│                   │    Architecture: dependency graph, API contracts
│                   │    Correctness: type hierarchy, similar implementations
│                   │  Predictive queries: co-change, missing tests, stale docs
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Governance Engine │  Risk scoring
│                   │  AI provenance detection
│                   │  Agent selection (which constellation members to invoke)
│                   │  Policy evaluation
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Agent             │  Paperclip dispatches agents in parallel
│ Constellation     │  Each agent: specialized context + prompt + LLM call
│                   │  Self-reflection pass per agent
│                   │  Evidence verification against CSG
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Meta-Agent        │  Aggregate, deduplicate, rank
│                   │  Apply confidence thresholds
│                   │  Apply team calibration
│                   │  Resolve conflicts
│                   │  Generate coherent review narrative
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Publisher          │  Pending review pattern (atomic submission)
│                   │  Check Run with annotations
│                   │  Severity-ranked inline comments
│                   │  Governance labels and metadata
│                   │  Audit record to governance store
└──────────────────┘
```

**Latency target:** 60-120 seconds for a standard PR (10 files, 500 lines). The constellation's parallel execution means total latency is bounded by the slowest agent, not the sum of all agents. Deterministic analysis (AST-grep, graph queries, predictions) completes in < 5 seconds. LLM calls are the long pole at 15-45 seconds each.

**Cost target:** Sonnet-class models for most agents. Opus-class only for Security Agent's deep analysis and Meta-Agent's conflict resolution. Estimated $0.30-0.60 per standard PR, $1.50-3.00 per large PR. Prompt caching on system prompts + cached CSG summaries reduces input costs up to 90%.

---

## 7. Technology Choices

### Language: Rust Core + Python Agents

**Rust for the performance-critical path:**
- CSG indexing pipeline (AST parsing, graph construction, embedding management)
- Diff processing (token-aware chunking, hunk extension)
- Webhook server (Axum — async, high-throughput)
- Compiled to a single binary for self-hosted deployment
- WASM compilation target for potential browser/editor integration

**Python for agent logic:**
- LLM integration (Anthropic SDK, LiteLLM for multi-provider)
- Prompt engineering (Jinja2 templates, Pydantic schemas)
- Paperclip agent runtime
- Rapid iteration on review logic without recompiling

**Why not all-Python:** The indexing pipeline processes entire codebases. Greptile's v3 struggled with memory management and workflow durability during indexing. Rust eliminates entire classes of bugs (memory safety, thread safety) and provides 10-100x performance for the compute-intensive graph construction. The review agents don't need this performance — they're I/O bound (waiting for LLM responses).

**Why not all-Rust:** LLM ecosystem is Python-first. Prompt engineering requires rapid iteration. Paperclip's agent SDK is Python-native. Fighting the ecosystem adds cost without benefit for the agent layer.

### Key Dependencies

| Component | Technology | Rationale |
|---|---|---|
| **Webhook server** | Axum (Rust) | Async, zero-copy, handles 10K+ concurrent webhooks |
| **AST parsing** | tree-sitter (Rust bindings) | Universal, incremental, production-proven |
| **Pattern matching** | ast-grep (Rust) | YAML-defined patterns over ASTs, language-agnostic |
| **Graph database** | SurrealDB (embedded) | Graph + document + vector, single binary, Rust core |
| **Embeddings** | Voyage-code-3 @ 1024d | SOTA code retrieval, Matryoshka for flexibility |
| **LLM (primary)** | Claude Sonnet 4.5 | Best cost/quality ratio, 200K context, structured output |
| **LLM (deep analysis)** | Claude Opus 4.6 | Extended thinking for security analysis, conflict resolution |
| **LLM (descriptions)** | Claude Haiku 4.5 | Fast, cheap semantic descriptions during indexing |
| **Agent orchestration** | Paperclip | Multi-agent, governance, budget tracking, provenance |
| **Prompt templates** | Jinja2 + Pydantic | Flexible rendering + typed structured output |
| **Token counting** | tiktoken | Fast, model-aware |
| **GitHub integration** | GitHub App (Rust + Octocrab) | Highest rate limits, Checks API, bot identity |
| **Configuration** | TOML (`.kenjutsu.toml`) | Simple, human-readable, version-controllable |
| **Task queue** | NATS JetStream | Lightweight, embeddable, persistent, handles backpressure |

### What Makes This Stack Innovative

1. **SurrealDB as a unified intelligence store.** Instead of separate vector DB + document store + graph DB, one engine handles all three. This dramatically simplifies deployment and eliminates synchronization issues between stores.

2. **Rust + Python split along the performance boundary.** The indexing pipeline (Rust) can process a million-line codebase in minutes. The review agents (Python) iterate rapidly on prompt engineering. Neither language fights its ecosystem.

3. **NATS JetStream for event-driven architecture.** Webhooks → NATS → agents. This decouples the webhook server from review processing, enabling: backpressure handling, retry semantics, multi-consumer patterns (analytics, audit, review all subscribe to the same event stream), and horizontal scaling.

4. **Single-binary self-hosted deployment.** The Rust core (webhook server + CSG engine + NATS) compiles to one binary. The Python agents run as Paperclip-managed processes. Total deployment: one binary + Python runtime. No Kubernetes required for small teams.

---

## 8. Cross-Repository Intelligence

### The Unoccupied Gap

No competitor does multi-repo well. Greptile explicitly struggles. CodeRabbit doesn't attempt it. This is Kenjutsu's most aggressive differentiation vector.

### Architecture

**Organization-level CSG.** The graph spans all repositories in an organization. Cross-repo edges are first-class:

- **API contract edges:** OpenAPI specs, GraphQL schemas, gRPC proto files are parsed and linked to their consumers across repos. When a service changes its API, the CSG knows every consumer.
- **Shared library edges:** Package dependencies (npm, pip, cargo) create edges between the library repo and consuming repos. Version constraints are tracked.
- **Data schema edges:** Database schemas, event schemas (Avro, Protobuf) link to every reader/writer across the org.
- **Deploy dependency edges:** Service dependency graphs (from docker-compose, Kubernetes manifests, Terraform) establish runtime coupling.

### Cross-Repo Review Scenarios

**Scenario 1: API breaking change.** Service A changes a REST endpoint's response schema. The CSG identifies services B, C, and D as consumers. The Architecture Agent flags: "This breaking change affects 3 services. Services B and C pin to the old schema via a shared client library (repo: shared-clients, line 142). Service D calls directly (service-d/src/api/client.ts:87)."

**Scenario 2: Shared library vulnerability.** A security advisory affects a library used by 12 repos. The Security Agent queries the CSG for all consumers and their version constraints, producing a prioritized remediation plan.

**Scenario 3: Architectural drift.** A team adopts a new pattern in service A. The Architecture Agent notices that services B and C (same team) still use the old pattern, and the new pattern contradicts the organization's architecture decision record. It flags both the drift and the ADR conflict.

---

## 9. Feedback Learning System

### Closing the Loop

The 19% → 55% improvement in Greptile's addressed-comment rate (from their feedback loop) validates that learning from team feedback is transformative. Kenjutsu takes this further.

### Per-Agent Learning

Each agent in the constellation learns independently:

- **Accepted findings** reinforce the agent's patterns (positive signal)
- **Rejected findings** are analyzed: was it a false positive (bad detection), irrelevant (wrong context), or team preference (valid but not wanted)? Each classification triggers different learning:
  - False positive → adjust detection threshold or add negative pattern
  - Irrelevant → adjust context retrieval strategy
  - Team preference → add to team-specific rule set
- **Ignored findings** (neither accepted nor rejected) are tracked separately — a high ignore rate signals noise

### Team Calibration Model

Each team develops a calibration profile over time:

- Noise tolerance (strict → permissive)
- Focus areas (security-heavy vs performance-heavy vs correctness-heavy)
- Convention preferences (specific naming patterns, error handling styles, test patterns)
- Override history (what the team consistently disagrees with)

This profile is stored in the CSG and applied by the Meta-Agent during review aggregation. A new team starts with conservative defaults. After ~50 PRs of feedback, the system is calibrated to the team's preferences.

### Privacy-First Learning

All learning is **local to the organization.** No team data, feedback, or code leaves the deployment. The learning model is a set of rules, thresholds, and embedding vectors stored in the CSG — not a fine-tuned LLM. This is critical for self-hosted enterprise deployment.

---

## 10. Trade-offs and Risks

### Ambitious Bets

| Bet | Upside | Downside | Mitigation |
|---|---|---|---|
| **Code Semantic Graph** | Transforms review quality; enables predictions and cross-repo | Complex to build and maintain; significant indexing infrastructure | Start with single-repo graph; add cross-repo incrementally. Indexing pipeline is background — review works with partial graph. |
| **Rust + Python split** | Performance + ecosystem flexibility | Two-language codebase; hiring complexity | Clear boundary (Rust = infrastructure, Python = intelligence). FFI via PyO3 is mature. |
| **Multi-agent constellation** | Specialized, parallel, governable | Higher per-review cost (multiple LLM calls); orchestration complexity | Governance Engine selects agents per-PR — simple PRs get fewer agents. Paperclip handles orchestration. |
| **SurrealDB** | Unified store, simple deployment | Younger project; less battle-tested than PostgreSQL + pgvector | CSG schema is portable. If SurrealDB proves unstable, migrate to PostgreSQL (graph via recursive CTEs + pgvector for embeddings). |
| **Cross-repo intelligence** | Unique differentiator; massive enterprise value | Requires organization-level access; indexing cost scales with org size | Gate behind enterprise tier. Start with explicit cross-repo declarations (config-driven), evolve to automatic discovery. |
| **Feedback learning** | Improves over time; reduces false positives | Cold start problem; requires ~50 PRs before meaningful calibration | Ship with strong defaults. Learning is additive (improves over defaults, never degrades below them). |

### What Could Go Wrong

1. **CSG indexing is too slow for large codebases.** Mitigation: Merkle-tree change detection ensures incremental updates are fast. Initial index can run in background — reviews work with whatever context is available.

2. **Multi-agent cost is prohibitive.** Mitigation: The Governance Engine is a cost dial. Most PRs trigger 2-3 agents (Correctness + one specialist), not the full constellation. Haiku-class models for simple agents keep costs low.

3. **SurrealDB doesn't scale.** Mitigation: The CSG schema is defined as a logical model. The storage engine is an implementation detail. PostgreSQL with pgvector + recursive CTEs is the fallback. We lose the single-binary story but keep the architecture.

4. **Rust development velocity is too slow.** Mitigation: The Rust surface area is bounded (indexing pipeline + webhook server). Review logic (the part that changes most) is all Python. Rust components stabilize early and change infrequently.

5. **Graph queries are too slow for real-time review.** Mitigation: Pre-compute common query patterns (callers, co-change sets, test mappings) as materialized views in the CSG. Queries that miss the cache fall back to on-demand traversal with a timeout.

---

## 11. Phased Delivery

### Phase 0: Foundation (Weeks 1-6)

- Rust webhook server (Axum) with HMAC-SHA256 verification
- GitHub App registration and token management
- Diff processor (tree-sitter hunk extension, token-aware chunking)
- Single-agent review (Correctness Agent in Python via Paperclip)
- Publisher (pending review pattern, Check Runs)
- **Milestone:** Reviews real PRs with one agent, no graph, heuristic context only

### Phase 1: Code Semantic Graph (Weeks 7-14)

- tree-sitter AST extraction pipeline (Rust)
- Semantic description generation (Haiku batch processing)
- Voyage-code-3 embedding pipeline with content-hash caching
- SurrealDB graph construction (structural + temporal edges)
- Graph-enhanced context retrieval for the Correctness Agent
- **Milestone:** Single-agent review with full codebase context via CSG

### Phase 2: Agent Constellation (Weeks 15-20)

- Security Agent with taint analysis prompts
- Architecture Agent with dependency graph queries
- Meta-Agent for aggregation, deduplication, ranking
- Confidence classification system
- Parallel agent execution via Paperclip
- **Milestone:** Multi-agent review with specialized findings and confidence scores

### Phase 3: Governance + Predictions (Weeks 21-26)

- Governance Engine (risk scoring, AI provenance detection, policy-as-code)
- Predictive Analysis Engine (co-change, missing tests, stale docs)
- Audit trail and compliance reporting
- Feedback learning system (per-agent, per-team calibration)
- **Milestone:** Governance-aware, predictive, learning review system

### Phase 4: Cross-Repo Intelligence (Weeks 27-32)

- Organization-level CSG spanning multiple repositories
- API contract analysis (OpenAPI, GraphQL, gRPC)
- Cross-repo impact detection
- Architectural drift detection
- **Milestone:** Multi-repo intelligence — the differentiator no competitor has

---

## 12. Why This Architecture Wins

**Against CodeRabbit:** CodeRabbit's multi-stage pipeline is a fixed sequence in a single process. Kenjutsu's constellation is a distributed, composable, governable multi-agent system. CodeRabbit has no cross-repo intelligence. CodeRabbit has no governance layer.

**Against Greptile:** Greptile's full-repo indexing is their moat — the CSG matches and exceeds it by adding graph structure (not just vector similarity) and cross-repo edges. Greptile's 11 false positives per benchmark run would be caught by the evidence-based confidence system. Greptile has no governance, no multi-agent specialization, and no self-hosted story.

**Against PR-Agent/Qodo:** PR-Agent is diff-only. Qodo 2.0's multi-agent is single-process. Both are AGPL (commercial dead end). Kenjutsu's architecture is fundamentally deeper in context, broader in scope, and cleaner in licensing.

**Against GitHub Copilot:** Copilot is a distribution play (1M users via bundling). Kenjutsu is a depth play. They are advisory-only, surface-level, diff-only. Kenjutsu is governance-aware, graph-powered, multi-agent. Different markets — Copilot wins adoption through convenience, Kenjutsu wins enterprises through capability.

**The moats:**
1. The Code Semantic Graph — takes months to build, impossible to shortcut
2. Paperclip-native multi-agent orchestration — no competitor has this infrastructure
3. Cross-repo intelligence — structurally impossible for single-repo tools to add
4. Governance engine — addresses regulatory deadlines (EU AI Act, Colorado AI Act) that create urgent enterprise demand
5. Feedback learning — compounds over time, making the product stickier with every review

---

## Summary

This architecture bets that the future of code review is not a better LLM prompt — it is a system that deeply understands the codebase, applies specialized analysis through multiple agents, proves its findings with evidence, and provides governance for the age of AI-generated code. Every component pushes beyond what current tools offer. The risk is proportional to the ambition: this is harder to build than a simple diff-reviewer, but if built, it creates a product that competitors cannot replicate by tuning their prompts.
