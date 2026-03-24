# Architecture Proposal: Balanced — Pragmatic Innovation

**Date:** 2026-03-23
**Author:** Chief Architect
**Issue:** DEM-120
**Parent:** DEM-117

---

## Design Philosophy

This architecture finds the sweet spot between proven approaches and strategic innovation. The guiding principle: **be conservative where failure cost is high, be ambitious where the risk-reward ratio is favorable.**

- **Conservative:** GitHub App integration, Python stack, build-from-scratch IP strategy, diff processing algorithms, webhook infrastructure — these are solved problems with known failure modes. Use proven patterns.
- **Ambitious:** Multi-agent review via Paperclip, natural language code descriptions for retrieval, governance-aware review pipeline, tiered context depth — these are differentiation vectors where the upside justifies the engineering investment.

The result is a system that ships a useful MVP quickly using battle-tested infrastructure, while building toward capabilities no competitor can replicate.

---

## 1. Core Architecture

### System Boundaries

Kenjutsu operates as three loosely coupled subsystems:

```
┌─────────────────────────────────────────────────────────────┐
│                     KENJUTSU SYSTEM                         │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Ingestion   │  │   Analysis   │  │   Orchestration  │  │
│  │   Subsystem   │→→│   Subsystem  │→→│   Subsystem      │  │
│  │              │  │              │  │   (Paperclip)    │  │
│  │ • Webhook    │  │ • Context    │  │ • Agent routing  │  │
│  │ • Diff proc  │  │ • Review     │  │ • Governance     │  │
│  │ • Git API    │  │ • Retrieval  │  │ • Publishing     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  Index Subsystem                     │    │
│  │  • AST parsing  • Embedding  • Incremental sync     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

**Ingestion** receives events, processes diffs, and interfaces with git platforms. This is plumbing — it should be reliable, fast, and boring.

**Analysis** retrieves context, generates review findings, and scores confidence. This is where intelligence lives — it should be deep, precise, and continuously improving.

**Orchestration** routes review tasks to specialized agents, enforces governance rules, and publishes results. This is the Paperclip-native layer — it should be composable, auditable, and unique.

**Index** runs asynchronously, building and maintaining the codebase knowledge graph. This is the context foundation — it should be incremental, cost-efficient, and resilient to staleness.

### Why Three Subsystems (Not One Pipeline)

A single pipeline (webhook → diff → LLM → comment) is what PR-Agent does. It's fast to build but creates a monolithic system where improving context depth means slowing down the whole review. Separating concerns lets us:

- Ship MVP with minimal Index subsystem (heuristic context only)
- Add deeper indexing without changing the Ingestion or Analysis interfaces
- Run multiple Analysis agents in parallel via Orchestration
- Scale each subsystem independently

The risk of over-separation is integration complexity. We mitigate this by keeping the interfaces simple: Ingestion produces a `ReviewRequest` (structured diff + metadata), Analysis consumes it and produces `ReviewFindings`, Orchestration routes and publishes.

---

## 2. Key Components

### 2.1 Ingestion: GitHub App + Webhook Server

**Approach: Proven (conservative)**

A GitHub App is non-negotiable. The rate limits (5,000-12,500 req/hr vs 1,000 for Actions), exclusive Checks API access, bot identity, and marketplace distribution make it the only production-viable choice. Every serious competitor uses this model.

**Components:**
- FastAPI webhook server with HMAC-SHA256 verification
- GitHub App authentication (JWT → installation token, 1-hour refresh cycle)
- Event routing for `pull_request` (opened, synchronize, reopened) and `issue_comment` events
- Async task dispatch via Redis queue (or in-process queue for MVP)
- PR metadata fetching, diff retrieval, file content access

**Secondary:** GitHub Action for zero-infrastructure onboarding. Same analysis logic, different trigger mechanism. This is a distribution play — lower barrier to entry for individual developers and small teams.

**Design decision:** Build the GitHub provider as a clean abstraction (`GitPlatformProvider` interface) from day one, but only implement GitHub initially. GitLab and Bitbucket are post-MVP. The abstraction costs almost nothing upfront and prevents a rewrite later.

**What we explicitly skip:** Raw webhook integration, OAuth App tokens, polling mode. These add maintenance burden without meaningful user value.

### 2.2 Diff Processing Pipeline

**Approach: Proven (conservative) — study PR-Agent, implement clean**

Diff processing is algorithmic work with well-understood solutions. PR-Agent has iterated on this for years. We study their approach and reimplement cleanly.

**Pipeline:**
1. Parse unified diff into structured `PatchFile` objects
2. Convert to decoupled hunk format (separate new/old views with line numbers) — this format helps LLMs reason about change positioning
3. Extend hunks to enclosing function/class boundaries via tree-sitter (dynamic context expansion)
4. Apply token-aware chunking: greedy fill within budget, language-prioritized ordering
5. Large diff handling: multi-patch mode (split into chunks, parallel LLM calls) for PRs exceeding token budget
6. Deletion omission: strip deletion-only hunks, list deleted files by name

**Token budget management:** Count tokens before every LLM call using tiktoken. Set model-aware limits (not PR-Agent's artificial 32K default). Reserve 10% output buffer. Graceful degradation — reduce context depth rather than fail.

**Trade-off acknowledged:** PR-Agent's token management is battle-tested but their 32K default cap wastes available context window. We set limits based on actual model capabilities (200K for Claude Sonnet 4.5, 100K+ for GPT-4o) with configurable overrides.

### 2.3 Context Retrieval: Tiered Depth

**Approach: Pragmatic innovation — cheap heuristics always, expensive retrieval when it matters**

This is where we diverge from PR-Agent (diff-only) without requiring Greptile's resource-intensive full-repo indexing from day one. The tiered approach lets us ship with meaningful context at low cost, then deepen it incrementally.

#### Tier 1 — Always On (Free, MVP)

These signals are computationally cheap and provide substantial context improvement over diff-only:

| Signal | Method | Cost |
|---|---|---|
| Enclosing scope | tree-sitter AST: expand hunks to function/class boundaries | Free (local parse) |
| Import graph | tree-sitter: extract imports, resolve to files in repo | Free (local parse) |
| Co-change files | `git log --follow` mining: files that historically change together | Free (git history) |
| Test file matching | Path heuristics: `foo.py` ↔ `test_foo.py`, `foo.spec.ts` | Free (pattern match) |
| Type definitions | tree-sitter: resolve type annotations to their definitions | Free (local parse) |

**Expected impact:** Moves us from PR-Agent's diff-only baseline toward CodeRabbit-level context awareness. Won't match Greptile's 82% bug detection rate, but will meaningfully outperform the 44% baseline of diff-only approaches.

#### Tier 2 — On-Demand (Medium Cost, Post-MVP Phase 1)

Activated for PRs that touch shared code, APIs, or cross-cutting concerns:

| Signal | Method | Cost |
|---|---|---|
| Semantic search | Voyage-code-3 embeddings (1024 dims) on function-level chunks | Medium (embedding API + vector query) |
| Hybrid retrieval | BM25 keyword + vector similarity, weighted 0.3/0.7 | Medium (dual index query) |
| Cross-encoder reranking | ms-marco-MiniLM or Cohere Rerank v3 on top-50 candidates → top-10 | Medium (reranking API call) |

**Key insight from research:** Embed natural language descriptions of code, not raw code. Greptile's data shows 12% retrieval improvement (0.8152 vs 0.7280 cosine similarity). The cost is an LLM call per chunk during indexing — but this is a one-time cost amortized across all reviews.

**Chunking strategy:** Function-level via tree-sitter AST. Include class header + imports with each chunk. No mid-function splitting. This is backed by both Greptile's empirical data (7% similarity drop from surrounding noise) and academic evidence (cAST, EMNLP 2025).

**Storage:** Voyage-code-3 at 1024 dimensions (92.28% of full 2048-dim quality, outperforms OpenAI-v3-large at 3072 dims). Binary quantization available for 32x storage reduction if needed at scale.

#### Tier 3 — Deep Analysis (Higher Cost, Post-MVP Phase 2)

For complex PRs, architectural changes, or security-sensitive reviews:

| Signal | Method | Cost |
|---|---|---|
| Agentic multi-hop search | LLM-guided dependency tracing through code graph | High (multiple LLM calls) |
| Historical review matching | Embed past review decisions, retrieve similar patterns | Medium (vector query) |
| Issue tracker context | Linked Jira/Linear/GitHub Issues for business context | Low (API call) |

**Trade-off:** Tier 3 is where we approach Greptile's depth. The cost is significant (multiple LLM calls per review), so it activates only for high-risk changes. The trigger heuristic: changes to shared libraries, API contracts, security-sensitive files, or changes flagged by specialized review agents.

### 2.4 Review Engine

**Approach: Proven foundation + pragmatic innovation in filtering**

#### LLM Integration

**Primary model: Claude Sonnet 4.5** — best cost/quality ratio for code review. 200K context window. Strong structured output. $0.22-0.35 per typical PR.

**Fallback: GPT-4o** — different model family reduces correlated failures. Similar quality tier at comparable cost.

**Deep analysis: Claude Opus 4.6** — reserved for self-reflection scoring and Tier 3 complex analysis. $1.10-1.75 per PR. Used only when the stakes justify the cost.

**Integration via LiteLLM** — unified interface to 100+ providers. Avoids vendor lock-in. Model-specific handling (temperature, system messages, reasoning effort) managed through a thin adapter layer, not scattered conditionals.

#### Prompt Architecture

Jinja2 templates with Pydantic schema-driven structured output. This is PR-Agent's strongest contribution — the pattern of embedding output schemas in prompts and parsing structured YAML/JSON responses is battle-tested.

**Template structure:**
```
System: Role definition + output schema (Pydantic model)
Context: Codebase summary + retrieved context chunks (cached)
Diff: Formatted hunks with line numbers
Instructions: Review criteria + severity definitions
```

**Prompt caching is critical.** Claude and OpenAI support prompt caching — up to 90% cost reduction for repeated system prompts + codebase summaries. The system prompt + cached context (60% of token budget) becomes near-free after the first review in a session.

#### False Positive Suppression

This is the most important quality metric. The research is unanimous: false positives are the #1 adoption killer across all tools. Our target: **<5% false positive rate.**

**Two-pass review:**
1. **Generation pass:** Primary LLM generates findings with severity and confidence scores
2. **Self-reflection pass:** Second LLM call (same or cheaper model) scores each finding 0-10 on relevance, accuracy, and actionability. Findings below threshold are suppressed.

**Innovation: Severity-first output.** Every finding is ranked: `critical` → `warning` → `info`. The review output leads with critical findings. Style nitpicks are suppressed by default (opt-in via configuration). This addresses the universal complaint that AI reviewers bury real bugs under style noise.

**Post-MVP: Feedback loop.** Track which findings developers accept vs dismiss. Use this signal to tune confidence thresholds per repository. Greptile's data shows this improved their addressed-comment rate from 19% to 55% within two weeks.

### 2.5 Orchestration: Paperclip-Native Multi-Agent Review

**Approach: Strategic innovation — our primary differentiation vector**

This is where Kenjutsu becomes something competitors cannot replicate. Every other tool runs review logic in a single process. We decompose review into specialized agents coordinated by Paperclip.

#### Agent Topology

```
                    ┌─────────────────┐
                    │  Review Router  │
                    │  (Orchestrator) │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───┐  ┌──────▼─────┐  ┌─────▼──────┐
     │  Security  │  │Performance │  │Architecture│
     │  Reviewer  │  │  Reviewer  │  │  Reviewer  │
     └────────────┘  └────────────┘  └────────────┘
```

**Review Router** receives a `ReviewRequest` from Ingestion, determines which specialized agents should review based on file types, change patterns, and repository configuration. Routes in parallel.

**Specialized Reviewers** each focus on one domain:
- **Security Reviewer:** OWASP patterns, taint analysis, credential detection, dependency vulnerabilities. Uses AST-grep rules for deterministic pattern matching + LLM for semantic security reasoning.
- **Performance Reviewer:** Algorithmic complexity, resource management, caching patterns, database query efficiency. Activated for files matching performance-sensitive paths.
- **Architecture Reviewer:** API contract changes, dependency direction violations, module boundary crossings, naming/pattern consistency. Uses the code graph from Tier 2 context.

**Key design choice:** Start with a single general-purpose reviewer in MVP. Add specialized agents incrementally. The Router's logic is simple initially (send everything to the general reviewer) but the routing interface exists from day one. This avoids the trap of building a monolithic reviewer and trying to decompose it later.

#### Governance Layer

**Innovation: Agent provenance and audit trails**

Every review finding carries metadata:
- Which agent produced it
- What context was available
- What model was used
- Confidence score

This enables:
- **Proportional approval workflows:** High-risk findings (security critical, from high-confidence analysis) can block merge. Low-confidence style suggestions are advisory only.
- **Compliance audit trails:** For regulated industries, every review decision is attributable and reproducible.
- **Trust scoring:** Over time, build a trust profile per agent based on acceptance rates. Low-trust agents get their thresholds raised automatically.

**Why this matters now:** EU AI Act (August 2026) and Colorado AI Act (June 2026) create regulatory demand for provenance tracking on AI-generated and AI-reviewed code. No competitor has this. The governance layer is cheap to build (metadata on findings) but expensive to retrofit.

### 2.6 Publisher

**Approach: Proven (conservative)**

**Pending review pattern:** Create review → accumulate all comments → submit atomically. One notification to the PR author, not N. This is what CodeRabbit and PR-Agent do — it's the correct UX.

**Dual output:**
- **PR Review:** Inline comments on specific lines, suggestion blocks for one-click fixes, overall review summary
- **Check Run:** Summary status (pass/fail), annotation count, rich markdown output. GitHub Apps exclusive — gives us the status check integration for branch protection.

**Rate limit awareness:** The content creation limit (80 req/min, 500 req/hr) is the binding constraint. Batch aggressively. For large PRs, prioritize findings rather than exhaustively commenting.

### 2.7 Index Subsystem

**Approach: Pragmatic innovation — incremental, cost-efficient**

The Index runs asynchronously, separate from the review hot path. It builds and maintains the codebase knowledge that Tier 2 and Tier 3 context retrieval consume.

**Indexing pipeline:**
1. tree-sitter AST parse → extract functions, classes, imports, type definitions
2. Generate natural language descriptions per function (LLM call — one-time cost)
3. Embed descriptions with Voyage-code-3 at 1024 dimensions
4. Store in vector database (LanceDB embedded for MVP, Qdrant for scale)
5. Build code graph: function calls, imports, type relationships

**Incremental sync:** Content-hash each chunk. On file change, re-chunk, compare hashes, only re-embed changed chunks. Inspired by Cursor's Merkle tree approach. Reduces embedding API costs 90%+ for typical daily changes.

**Trigger:** Re-index on PR creation against base branch. Full re-index on default branch merge. Staleness tolerance is higher for review tools than IDE tools — we don't need real-time indexing.

**Trade-off:** The natural language description step adds an LLM call per function during indexing. For a 100K-function codebase, initial indexing costs ~$50-100 in LLM calls. Subsequent incremental updates are negligible. This is a worthwhile one-time investment for the 12% retrieval improvement.

---

## 3. Data Flow

### Happy Path: PR Review

```
1. GitHub sends pull_request webhook (opened/synchronize)
   └→ Webhook server verifies HMAC-SHA256 signature
   └→ Enqueues ReviewRequest to task queue

2. Ingestion worker picks up task
   └→ Fetches PR metadata (title, description, commits, files)
   └→ Fetches diff via GitHub API
   └→ Processes diff: parse → decouple hunks → extend context → chunk
   └→ Produces structured ReviewRequest

3. Orchestration (Review Router) receives ReviewRequest
   └→ Determines which reviewers to activate (MVP: general only)
   └→ Routes to reviewers in parallel

4. Analysis (each reviewer independently):
   └→ Tier 1 context retrieval (import graph, co-change, test files)
   └→ [If indexed] Tier 2 context retrieval (semantic search, reranking)
   └→ Renders prompt with diff + context + instructions
   └→ LLM call → structured findings
   └→ Self-reflection pass → filtered, scored findings

5. Orchestration collects findings from all reviewers
   └→ Deduplicates across reviewers
   └→ Applies governance rules (severity thresholds, team config)
   └→ Ranks findings: critical → warning → info

6. Publisher posts results
   └→ Creates pending review with inline comments
   └→ Submits review atomically (single notification)
   └→ Creates Check Run with summary annotations
```

### Timing Expectations

| PR Size | Files | Lines Changed | Context Tier | Expected Latency | Estimated Cost |
|---|---|---|---|---|---|
| Small | 1-5 | <200 | Tier 1 only | 15-30s | $0.10-0.20 |
| Typical | 5-15 | 200-800 | Tier 1 + Tier 2 | 30-60s | $0.20-0.40 |
| Large | 15-50 | 800-2000 | Tier 1 + Tier 2 | 60-120s (multi-patch) | $0.50-1.50 |
| Very Large | 50+ | 2000+ | Tier 1 + Tier 2 + selective Tier 3 | 120-300s | $1.50-5.00 |

---

## 4. Technology Choices

### Language: Python

**Rationale:** Best LLM ecosystem (LiteLLM, tiktoken, Anthropic SDK), mature tree-sitter bindings (py-tree-sitter), FastAPI for async webhooks, PyGithub for GitHub API. PR-Agent's architecture (studied, not forked) is Python — learnings transfer directly.

**Alternative considered: TypeScript.** Closer to GitHub/VS Code ecosystem. Better for future IDE extensions. But weaker LLM library ecosystem and tree-sitter support in 2026. Revisit for IDE components post-MVP.

### Key Dependencies

| Library | Purpose | Why |
|---|---|---|
| FastAPI | Webhook server | Async, high-performance, well-documented |
| LiteLLM | Multi-LLM provider | 100+ providers, unified interface, avoids lock-in |
| py-tree-sitter | AST parsing | Universal parser, production-proven (Neovim, Zed) |
| tiktoken | Token counting | Fast, accurate, model-aware |
| Voyage-code-3 | Code embeddings | SOTA for code retrieval, Matryoshka dimensions |
| LanceDB | Vector storage (MVP) | Embedded, zero-infra, good Python support |
| PyGithub | GitHub API | Mature, well-maintained |
| Jinja2 | Prompt templates | Flexible conditional rendering |
| Pydantic | Structured output | Type validation, JSON schema generation |
| Redis (or dramatiq) | Task queue | Async processing, debouncing |

### What We Explicitly Avoid

- **Dynaconf** — PR-Agent's global state pattern (200+ `get_settings()` calls) is their worst architectural decision. Use explicit configuration injection via Pydantic settings.
- **Monolithic dependencies** — Use optional extras: `pip install kenjutsu[github]`, `kenjutsu[embeddings]`. Don't force boto3 on users who only need GitHub.
- **Hardcoded command registry** — Design a plugin system from day one. Even if MVP has one review command, the extension point exists.

---

## 5. Configuration

### User-Facing Configuration

`.kenjutsu.toml` in repository root. Zero-config operation with sensible defaults. Override only what you need.

```toml
[kenjutsu]
# Review behavior
auto_review = true              # Review on PR open/push
review_on_draft = false         # Skip draft PRs
severity_threshold = "warning"  # Minimum severity to comment (critical/warning/info)

[kenjutsu.context]
# Context depth
tier = "auto"                   # auto | tier1 | tier2 | tier3
# auto: Tier 1 always, Tier 2 for shared code, Tier 3 for high-risk

[kenjutsu.ignore]
# Files to skip
paths = ["*.lock", "*.generated.*", "vendor/", "node_modules/"]

[kenjutsu.model]
# LLM selection (defaults to optimal choices)
primary = "claude-sonnet-4-5"
fallback = "gpt-4o"
```

**Design principle:** Defaults should produce good results for 90% of repositories. Configuration is for tuning, not setup.

---

## 6. Trade-offs and Rationale

### What We Gain vs What We Risk

| Decision | What We Gain | What We Risk | Mitigation |
|---|---|---|---|
| Build from scratch (not fork) | Clean IP, optimal architecture, no AGPL | 10-14 weeks vs 2-4 for fork | Study PR-Agent's patterns to avoid re-inventing solved problems |
| Tiered context (not full index from day one) | Faster MVP, lower initial cost | Tier 1 quality gap vs Greptile | Tier 1 still beats diff-only significantly; Tier 2 planned for Phase 2 |
| Multi-agent via Paperclip | Unique differentiation, governance capability | Coupling to Paperclip, orchestration overhead | Single-reviewer MVP works without multi-agent; agents add incrementally |
| Natural language code descriptions | 12% retrieval improvement | LLM cost during indexing (~$50-100 for large codebases) | One-time cost, amortized across all reviews. Incremental re-indexing is cheap |
| Python (not TypeScript) | Best LLM ecosystem, faster MVP | Weaker for future IDE extensions | IDE components can be TypeScript; core analysis stays Python |
| Precision over recall | Developer trust, lower noise | May miss some real issues | Self-reflection pass catches most; feedback loop improves over time |
| GitHub-first (not multi-platform) | Focused effort, faster shipping | Excludes GitLab/Bitbucket users initially | Provider abstraction exists from day one; add platforms post-MVP |

### Decisions We Defer (and Why)

| Decision | Deferral Rationale | When to Decide |
|---|---|---|
| Multi-repo intelligence | Requires significant index infrastructure; single-repo is sufficient for MVP and early adoption | After Tier 2 context is proven (Phase 3+) |
| Pre-commit / IDE integration | Different integration surface; PR review is the established user expectation | After core review quality is validated |
| Feedback loop learning | Needs volume of review data to be useful | After 1000+ reviews across real repositories |
| Agentic multi-hop search (Tier 3) | High cost, complex implementation; Tier 1+2 covers most cases | After measuring Tier 2 impact on bug detection |

---

## 7. Phased Delivery

### Phase 1: Foundation (Weeks 1-4)

**Goal:** Working GitHub App that can receive PRs, process diffs, and post basic review comments.

- GitHub App registration, webhook server, signature verification
- GitHub provider (auth, diff fetching, file retrieval, review publishing)
- Diff processor (parsing, hunk formatting, token budgeting, chunking)
- Configuration system (`.kenjutsu.toml` with defaults)
- CLI for local testing

**Exit criteria:** Can receive a PR webhook, fetch diff, process it, and post a raw diff summary as a PR comment.

### Phase 2: Review Intelligence (Weeks 5-8)

**Goal:** Meaningful review quality with Tier 1 context and false positive filtering.

- LLM integration via LiteLLM, prompt templates, structured output
- Review engine (severity scoring, finding generation, Markdown formatting)
- Tier 1 context (tree-sitter import graph, dynamic hunk extension, co-change analysis)
- Self-reflection pass for false positive filtering
- Publisher (pending review pattern, Check Runs)

**Exit criteria:** Reviews real PRs with context-aware findings, severity ranking, and <10% false positive rate. Posts as a proper GitHub review with inline comments.

### Phase 3: Polish & Hardening (Weeks 9-12)

**Goal:** Production-ready MVP.

- Prompt engineering iteration on real PRs (target: <5% FP rate)
- Large PR handling (multi-patch mode), edge cases, error handling
- Paperclip orchestration integration (Review Router, single general reviewer)
- Governance metadata on findings (agent, model, confidence)
- Deployment packaging (Docker), documentation
- Internal benchmark suite

**Exit criteria:** Can be installed on real repositories. Governance metadata attached to all findings. Deployable via Docker.

### Phase 4: Context Depth (Weeks 13-16, Post-MVP)

**Goal:** Tier 2 context for significantly improved bug detection.

- Index subsystem: tree-sitter AST → natural language descriptions → Voyage-code-3 embeddings
- Incremental indexing with content-hash caching
- Hybrid BM25 + vector retrieval, cross-encoder reranking
- Prompt caching optimization
- Performance benchmarking vs competitors

**Exit criteria:** Full codebase context during review. Measurable improvement in bug detection rate over Tier 1 baseline.

### Phase 5: Multi-Agent & Governance (Weeks 17-20, Post-MVP)

**Goal:** Specialized review agents and enterprise governance.

- Security Reviewer agent (AST-grep patterns + LLM security reasoning)
- Performance Reviewer agent
- Review Router with file-type-based routing
- Governance dashboard (finding provenance, trust scores)
- GitHub Action distribution for zero-infra onboarding

**Exit criteria:** Multiple specialized agents reviewing PRs in parallel. Governance audit trail complete for compliance use cases.

---

## 8. Infrastructure and Cost Projections

### MVP Infrastructure (Phases 1-3)

| Component | Requirement | Monthly Cost |
|---|---|---|
| Webhook server | Single container, 1 vCPU, 1GB RAM | $20-50 |
| Task queue | Redis (or in-process for small scale) | $0-15 |
| Configuration store | Filesystem or SQLite | $0 |
| Monitoring | Structured logging + error tracking | $0-30 |
| **Total infrastructure** | | **$20-95** |

### Post-MVP Infrastructure (Phases 4-5)

| Component | Requirement | Monthly Cost |
|---|---|---|
| Vector database | LanceDB (embedded) → Qdrant (hosted) | $0-100 |
| Embedding service | Voyage AI API | $0.06-0.12/1M tokens |
| Persistent storage | S3/GCS for embedding cache | $5-20 |
| Background workers | For indexing/re-indexing | $30-100 |
| **Total post-MVP additions** | | **$35-320** |

### LLM Cost per Review (Claude Sonnet 4.5, primary)

| PR Size | Input Tokens | Output Tokens | Cost (no caching) | Cost (with caching) |
|---|---|---|---|---|
| Small (1-5 files) | ~30K | ~3K | $0.14 | $0.06 |
| Typical (5-15 files) | ~60K | ~5K | $0.26 | $0.10 |
| Large (15-50 files, multi-patch) | ~200K | ~15K | $0.83 | $0.31 |

**Prompt caching reduces ongoing LLM costs by 60-90%.** The system prompt + codebase index summary is stable across reviews within the same repository. This is the single most impactful cost optimization.

---

## 9. Risk Assessment

### Risks We Accept

| Risk | Likelihood | Impact | Why We Accept It |
|---|---|---|---|
| Prompt engineering iteration takes longer than budgeted | High | Medium | This is empirical work, not architecture. Budget 3-4 weeks. The risk is schedule, not feasibility. |
| Tier 1 context quality gap vs Greptile | High | Medium | Tier 1 still beats diff-only. Tier 2 is planned. We compete on precision, not just detection rate. |
| Paperclip dependency for multi-agent | Medium | Medium | Single-reviewer mode works standalone. Multi-agent is additive differentiation, not a prerequisite. |

### Risks We Mitigate

| Risk | Mitigation |
|---|---|
| False positive rate above target | Two-pass review (generation + self-reflection). Severity ranking. Feedback loop post-MVP. Design for precision from day one. |
| LLM API reliability | Fallback chain across providers (Claude → GPT-4o). Retry with exponential backoff. Different model families reduce correlated failures. |
| Context window management | Rigorous token counting before every call. Graceful degradation (reduce context, don't fail). Model-aware limits, not artificial caps. |
| GitHub rate limits | Pending review pattern (batch comments). Check Run annotations (50 per call). Debounce on PR updates (30-60s wait). |
| IP/legal risk from studying PR-Agent | Clean-room reimplementation. Study patterns and strategies, not code. No post-AGPL code contact. Legal review of prompt engineering reuse. |

### Risks We Avoid

| Risk | How We Avoid It |
|---|---|
| AGPL contamination | Build from scratch. No fork. Study only, implement independently. |
| Vendor lock-in | LiteLLM for LLM providers. Provider abstraction for git platforms. Standard vector DB interfaces. |
| Premature scaling | MVP runs on a single container. Scale when we have users, not before. |
| Feature bloat | MVP is `/review` only. No `/describe`, `/improve`, `/ask` until core review quality is proven. |

---

## 10. What Makes This "Balanced"

This architecture is balanced because it makes different bets at different layers:

**We bet conservatively on infrastructure** — GitHub App, Python, FastAPI, Redis, Docker. These are boring, proven choices. The failure mode is "it doesn't work" and the blast radius is "the team wastes time." Boring infrastructure reduces that risk to near-zero.

**We bet pragmatically on context** — Tiered retrieval lets us ship with Tier 1 (free, heuristic) and add Tier 2 (embeddings, semantic search) when we have the data to justify it. We don't gamble on full-repo indexing working at scale before proving basic review quality.

**We bet ambitiously on orchestration** — Multi-agent review via Paperclip is genuinely novel. No competitor has this. The risk is that the multi-agent overhead outweighs the specialization benefit, but the mitigation is clean: single-reviewer MVP works without it, and we add agents incrementally based on evidence.

**We bet ambitiously on governance** — The regulatory tailwind (EU AI Act, Colorado AI Act) creates demand that doesn't exist yet but will by the time we ship Phase 5. Building governance metadata into findings from Phase 3 is cheap insurance against an expensive retrofit.

The result: a system that is useful from week 8 (basic review with good precision), differentiated by week 16 (deep context + multi-agent), and enterprise-ready by week 20 (governance + compliance). Each phase delivers standalone value — no phase depends on a future phase to be useful.

---

## Sources

This architecture synthesizes findings from:
- Competitive analysis (DEM-105): Market positioning, pricing, feature gaps
- PR-Agent deep-dive (DEM-106): Architecture patterns, diff processing, prompt engineering
- GitHub integration (DEM-107): App vs Action, rate limits, API patterns
- Context/RAG strategies (DEM-108): Embedding approaches, chunking, retrieval pipelines
- Differentiation (DEM-109): Market gaps, positioning options, governance opportunity
- Technical feasibility (DEM-110): Build vs fork, MVP scope, timeline, cost projections
