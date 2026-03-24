# Architecture Proposal: Pragmatic — Best Possible Given Current Knowledge

**Date:** 2026-03-24 (v2 — revised per board feedback)
**Author:** Chief Architect
**Issue:** DEM-118
**Parent:** DEM-117

---

## Design Philosophy

This architecture optimizes for **highest probability of shipping a useful product.** Every choice favors proven technology, well-understood patterns, and incremental buildability over novelty. The goal is not to push boundaries — it is to deliver a code review tool that developers actually want to use, built on foundations we are confident will work.

The pragmatic lens means:
- Choose boring technology when it works
- Ship the simplest thing that solves the problem, then iterate
- Never add complexity to solve problems we don't yet have
- Every component earns its place by solving a concrete, immediate need

---

## Assumptions We Challenge

### 1. "Build from scratch is clearly the right path"

The research unanimously recommends building from scratch over forking PR-Agent. The reasoning is sound (AGPL blocks commercial use, v0.29 fork carries significant tech debt), but we should acknowledge what we give up: PR-Agent has years of prompt engineering iteration, real-world edge case handling, and community-contributed improvements. Building from scratch means rediscovering these lessons empirically. Budget for it — the 10-14 week estimate is optimistic if prompt tuning takes the 3-4 weeks the research predicts.

**Our position:** Build from scratch, but study PR-Agent more deeply than the research suggests. Don't just study "strategies" — systematically catalog their prompt evolution (git history of prompt TOML files), their edge case handling (issues and bug fixes), and their configuration surface area. This catalog becomes our test case library.

### 2. "Python is the obvious language choice"

Every research document assumes Python. The rationale (best LLM ecosystem, tree-sitter bindings, FastAPI) is valid, but consider: the GitHub platform ecosystem is JavaScript/TypeScript-native. GitHub Actions are Node.js. VS Code extensions are TypeScript. GitHub's own Copilot code review is likely TypeScript. By choosing Python, we optimize for the LLM ecosystem but create friction with the platform ecosystem. The DEM-114 evaluation notes that Mastra (TypeScript) has strong RAG capabilities we cannot use.

**Our position:** Python is still correct for MVP. But this is a genuine trade-off, not an obvious choice. Plan for TypeScript components post-MVP (GitHub Action wrapper, IDE extensions) and ensure the core review engine exposes clean APIs that TypeScript clients can consume.

### 3. "Layered context is sufficient — we don't need full indexing from day one"

The tiered approach (Layer 1 heuristics always, Layer 2 embeddings when needed) is pragmatically sound. But we should be honest: Layer 1 heuristics alone will produce reviews that are meaningfully shallower than Greptile or CodeRabbit. Import graph traversal and co-change analysis catch direct dependencies, but miss: cross-cutting concerns, convention violations in unmodified files, duplicate code elsewhere, and architectural pattern mismatches. These are exactly the findings that distinguish AI review from a linter.

**Our position:** Ship with Layer 1, but treat Layer 2 as "fast follow" (weeks 13-16), not "someday." The competitive gap between Layer 1 and full indexing is real and matters for positioning.

### 4. "Self-reflection reduces false positives to acceptable levels"

The two-pass approach (generate findings, then score them) is proven by PR-Agent's `/improve` tool. But the research may overstate its effectiveness. Self-reflection catches obvious false positives (wrong line numbers, findings contradicted by nearby context) but is less effective at catching subtle false positives (findings that are technically correct but not useful, or findings that miss team-specific conventions). The hard part of FP reduction is calibrating to what a specific team considers noise — and that requires data we won't have at launch.

**Our position:** Self-reflection is necessary but not sufficient. Target <10% FP for MVP (realistic), not <5% (aspirational). Build the feedback collection mechanism (accept/reject signals) from day one, even if the learning system comes later.

### 5. "The governance opportunity justifies architectural investment"

The regulatory tailwind (EU AI Act, Colorado AI Act) is real, but the timeline is uncertain. Regulations may be delayed, weakened, or interpreted differently than expected. Building a full governance engine for a market that may not materialize for 12-18 months is a bet, not a certainty.

**Our position:** Add governance metadata to findings (cheap: agent ID, model, confidence, timestamp). Defer the governance dashboard, policy-as-code engine, and compliance reporting until there is customer demand or regulatory clarity. Metadata-in, dashboard-later is the pragmatic path.

---

## 1. Core Architecture

### System Overview

Kenjutsu is a linear processing pipeline with an optional asynchronous index. In a pragmatic architecture, simplicity is a feature — fewer moving parts means fewer failure modes.

```text
GitHub Webhook
       │
       ▼
┌──────────────┐
│ Webhook      │  FastAPI server, HMAC-SHA256 verification
│ Server       │  Event routing, async task dispatch
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ PR Processor │  Diff fetching, hunk formatting
│              │  tree-sitter context extension
│              │  Token-aware chunking
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Context      │  L1: Heuristics (always, free)
│ Retriever    │  L2: Semantic search (when needed, via LlamaIndex)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Review       │  Prompt rendering (Jinja2 + Pydantic)
│ Engine       │  LLM call via LiteLLM (Claude Sonnet 4.5)
│              │  Self-reflection pass → filter FPs
│              │  Governance metadata attachment
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Publisher    │  Pending review → submit atomically
│              │  Check Run with annotations
└──────────────┘
```

### Why a Pipeline (Not Microservices)

A pragmatic architecture is a single-process pipeline for MVP. Reasons:
- **Debuggable.** When a review is wrong, trace the full path in one process.
- **Deployable.** One container. No service mesh, no inter-service auth, no distributed tracing needed on day one.
- **Testable.** Integration tests run the full pipeline in-process.
- **Evolvable.** If we need to extract a service later (e.g., the Index subsystem), clean interfaces make that possible. But we don't pay the complexity cost until we need it.

The risk of a single-process pipeline is that it doesn't scale horizontally. For MVP, this doesn't matter — a single container handles hundreds of PRs per day. When scale demands it (>1000 PRs/day), extract the review engine as a worker pool behind Redis.

---

## 2. Key Components

### 2.1 Webhook Server

**Technology:** FastAPI (async, well-documented, community-standard for Python APIs)

- HMAC-SHA256 signature verification (mandatory — PR-Agent's CVEs demonstrate the consequences of skipping this)
- Event routing: `pull_request` (opened, synchronize, reopened), `issue_comment` (slash commands)
- Immediate acknowledgment (< 1 second) with background task dispatch
- Debounce on `synchronize` events (30-60 second wait for additional commits)
- Request-scoped configuration via Pydantic Settings (no global state, no Dynaconf)

### 2.2 Git Platform Provider

Clean `GitPlatformProvider` ABC with consistent return types. GitHub-only for MVP; the abstraction costs nothing and prevents a rewrite when GitLab is added.

**GitHub App authentication:** JWT (RS256, 10-min lifetime) → installation token (1-hour expiry). Proactive refresh. Minimum permissions: `pull_requests: write`, `checks: write`, `contents: read`, `metadata: read`.

**Rate limit strategy:** Pending review pattern (batch all comments, submit once). Check Run annotations (50 per API call). Debounce. Monitor `x-ratelimit-remaining` headers proactively.

### 2.3 Diff Processor

Studied from PR-Agent, reimplemented clean:

1. Parse unified diff into structured `FilePatch` objects
2. Convert to decoupled hunk format (separate new/old views with line numbers)
3. Extend hunks to enclosing function/class via tree-sitter AST queries
4. Token-aware chunking: greedy fill within model limits (actual limits, not PR-Agent's artificial 32K cap)
5. Large diff handling: multi-patch mode (parallel LLM calls, up to 3 chunks)
6. Deletion omission: strip deletion-only hunks, list deleted files by name

### 2.4 Context Retriever

#### Layer 1 — Always On (Free, MVP)

| Signal | Method | Cost |
|---|---|---|
| Enclosing scope | tree-sitter: expand hunks to function/class boundaries | Free |
| Import graph | tree-sitter: extract imports, resolve to files | Free |
| Co-change files | `git log` mining: historically coupled files | Free |
| Test file matching | Path heuristics: `foo.py` ↔ `test_foo.py` | Free |
| Type definitions | tree-sitter: resolve type annotations to definitions | Free |

#### Layer 2 — On Demand (Medium Cost, Post-MVP Fast Follow)

**Framework: LlamaIndex** (per DEM-114 evaluation). LlamaIndex provides the retrieval infrastructure; we provide the code-specific components.

| Kenjutsu Component | LlamaIndex Extension | Custom or Built-in |
|---|---|---|
| Function-level code chunking | Custom `CodeNodeParser` (tree-sitter) | Custom |
| Import graph retrieval | Custom `ImportGraphRetriever` | Custom |
| Co-change retrieval | Custom `CoChangeRetriever` | Custom |
| Test file matching | Custom `TestFileRetriever` | Custom |
| Semantic code search | `VectorIndexRetriever` + Voyage-code-3 | Built-in |
| Keyword search | `BM25Retriever` | Built-in |
| Hybrid search | `QueryFusionRetriever` (RRF) | Built-in |
| Reranking | `CohereRerank` | Built-in |
| Query routing | `RouterQueryEngine` | Built-in |

**Insulation layer:** Wrap all LlamaIndex interfaces behind our own abstractions. If LlamaIndex API churn or commercial pressure becomes untenable, Haystack (Apache-2.0) is the migration target.

**Embedding strategy:** Voyage-code-3 at 1024 dimensions. Embed natural language descriptions of code (12% retrieval improvement per Greptile data). Incremental indexing with content-hash caching.

### 2.5 Review Engine

**Two-pass review:**

1. **Generation pass:** Jinja2 prompt template → LLM call (Claude Sonnet 4.5 via LiteLLM) → Pydantic-validated structured findings with severity (critical/warning/info), confidence, evidence
2. **Self-reflection pass:** Second LLM call scores each finding on correctness, relevance, actionability. Filters below threshold (default: score >= 7). Validates line numbers against diff.

**Model selection:**
- Standard review: Claude Sonnet 4.5 ($0.22-0.35/PR, 200K context)
- Self-reflection: Same model or cheaper
- Fallback: GPT-4o (different model family, reduces correlated failures)
- Deep analysis (post-MVP): Claude Opus 4.6 for security-critical or complex PRs

**Prompt caching:** Non-negotiable for cost control. System prompt + codebase summary cached across reviews. Up to 90% input cost reduction.

**Governance metadata:** Every finding carries: agent ID, model used, context tier, confidence score, timestamp. This is cheap to add now and expensive to retrofit later.

### 2.6 Publisher

**Pending review pattern:** Create PENDING review → accumulate inline comments → submit atomically. One notification to the PR author.

**Dual output:**
- PR Review: inline comments with severity badges, suggestion blocks for one-click apply
- Check Run: summary status with annotations (pass/fail for branch protection)

**Severity presentation:** Critical (always shown) → Warning (shown by default) → Info (hidden by default). Silent by default — only comments on genuine issues.

### 2.7 Configuration

`.kenjutsu.toml` in repo root. Zero-config defaults that work for 90% of repos.

```toml
[kenjutsu]
auto_review = true
review_on_draft = false
severity_threshold = "warning"

[kenjutsu.context]
tier = "auto"

[kenjutsu.ignore]
paths = ["*.lock", "*.generated.*", "vendor/", "node_modules/"]

[kenjutsu.model]
primary = "claude-sonnet-4-5"
fallback = "gpt-4o"
```

---

## 3. Paperclip Integration

### MVP: Single Agent + Governance Metadata

One generalist review agent for MVP. Multi-agent orchestration is the long-term differentiator, but it adds complexity that is unjustified until we have evidence that specialization improves quality.

**What Paperclip provides in MVP:**
- Agent identity on every review finding (audit trail)
- Budget tracking (prevents unbounded LLM costs)
- Deployment flexibility (adapter model: runs locally, in CI, or hosted)

### Post-MVP: Evidence-Gated Multi-Agent

Add specialized agents only when MVP review data shows measurable quality gaps by domain:

```text
Coordinator Agent → routes to specialists based on file types / change patterns
├── Security Agent (if security gap demonstrated)
├── Performance Agent (if performance gap demonstrated)
└── Architecture Agent (if architecture gap demonstrated)
```

**Criteria:** The general reviewer must demonstrate a measurable quality gap in a specific domain across a significant sample of real reviews.

---

## 4. Data Flow

### Happy Path (Typical PR: 10 files, 500 lines)

```text
T+0s     GitHub webhook (pull_request opened)
T+0.1s   HMAC verify → ack 200 → enqueue async task
T+0.5s   Fetch PR metadata, diff, file list
T+1.5s   Parse diff → decoupled hunks → tree-sitter context extension
T+2.0s   Layer 1 context: import graph + co-change + test matching
T+2.5s   Token budget allocation within model limits
T+3.0s   Prompt rendering → LLM call (Claude Sonnet 4.5)
T+18s    Response parsing → Pydantic validation
T+18.5s  Self-reflection pass → filter FPs → attach governance metadata
T+28s    Publisher: format → pending review → submit atomically
T+29s    Check Run with annotation summary
T+30s    Done.
```

### Large PR Path (50+ files, 2000+ lines)

Multi-patch: split into 3-4 chunks → parallel LLM calls → aggregate → self-reflect → publish. Total: ~50-60 seconds.

### Incremental Review (New Commits)

Debounce 30-60s → diff new commits against last reviewed commit → normal pipeline on delta → dismiss stale findings.

---

## 5. Technology Choices

### Language: Python

Best LLM ecosystem (LiteLLM, tiktoken, Anthropic SDK), mature tree-sitter bindings, FastAPI, LlamaIndex-native. PR-Agent (studied, not forked) is Python. Fastest path to MVP.

Trade-off acknowledged: weaker for GitHub Action packaging and IDE extensions. Plan TypeScript wrappers for those surfaces post-MVP.

### Key Dependencies

| Library | Purpose | Why |
|---|---|---|
| FastAPI | Webhook server | Async, well-documented, community standard |
| LiteLLM | Multi-LLM provider | 100+ providers, unified interface |
| LlamaIndex | Retrieval orchestration (Layer 2) | Deepest retrieval primitives, code-specific extensions |
| py-tree-sitter | AST parsing | Universal, production-proven |
| tiktoken | Token counting | Fast, model-aware |
| Voyage-code-3 | Code embeddings | SOTA for code retrieval |
| LanceDB | Vector storage (MVP) | Embedded, zero-infra |
| PyGithub | GitHub API | Mature, well-maintained |
| Jinja2 | Prompt templates | Flexible, conditional rendering |
| Pydantic | Structured output + settings | Type validation, configuration management |

### What We Avoid

| Anti-pattern | Why | Alternative |
|---|---|---|
| Dynaconf / global state | PR-Agent's 200+ `get_settings()` = hidden coupling | Pydantic Settings, explicit injection |
| Monolithic deps | 35 deps regardless of provider | Optional extras: `kenjutsu[github]` |
| Hardcoded commands | Blocks extensibility | Plugin system with registration |
| 32K token cap | Wastes modern context windows | Actual model limits |
| Graph-RAG systems | LLM entity extraction is wrong for code (DEM-114) | tree-sitter AST for code graphs |

---

## 6. Trade-offs and Rationale

| Decision | What We Gain | What We Risk | Mitigation |
|---|---|---|---|
| Build from scratch | Clean IP, no AGPL, optimal architecture | 10-14 weeks (vs 2-4 fork) | Deep study of PR-Agent patterns |
| Single-process pipeline | Debuggable, deployable, testable | Doesn't scale horizontally | Extract workers when needed (>1K PRs/day) |
| LlamaIndex for Layer 2 | 7 built-in capabilities | API churn, abstraction overhead | Insulation layer, Haystack fallback |
| Layer 1 only for MVP | Ships fast, low cost | Shallower than competitors | Layer 2 as fast follow (weeks 13-16) |
| Single agent MVP | Simplicity, focus on core quality | No specialization | Evidence-gated agents post-MVP |
| Python only | Best ecosystem, fastest path | Friction with platform ecosystem | TypeScript wrappers post-MVP |
| <10% FP target | Realistic, achievable | Higher than aspirational <5% | Feedback loop for continuous improvement |
| Governance metadata only | Cheap to add, expensive to retrofit | No governance UI or policy engine | Build dashboard when demand exists |

---

## 7. Phased Delivery

### Phase 1: Foundation (Weeks 1-4)

- GitHub App registration, webhook server, signature verification
- Git platform provider (auth, diff fetching, file retrieval, review publishing)
- Diff processor (parsing, hunk formatting, token budgeting, chunking)
- Configuration system (`.kenjutsu.toml` with defaults)
- CLI for local testing

**Exit criteria:** Receives PR webhook, fetches diff, posts formatted summary.

### Phase 2: Review Intelligence (Weeks 5-8)

- LLM integration via LiteLLM, Jinja2 prompt templates, Pydantic structured output
- Review engine (severity scoring, finding generation)
- Layer 1 context (tree-sitter import graph, hunk extension, co-change, test matching)
- Self-reflection pass for FP filtering
- Publisher (pending review pattern, Check Runs)

**Exit criteria:** Reviews real PRs with severity ranking and <10% FP rate.

### Phase 3: Production Hardening (Weeks 9-12)

- Prompt engineering iteration on real PRs
- Large PR handling (multi-patch), edge cases, error handling
- Paperclip integration (single agent, governance metadata)
- Deployment packaging (Docker), documentation
- Internal benchmark suite

**Exit criteria:** Production-ready. Installable on real repos. Benchmarked against competitors.

### Phase 4: Context Depth (Weeks 13-16, Fast Follow)

- LlamaIndex integration: custom NodeParser, custom retrievers
- Voyage-code-3 embeddings with NL descriptions
- Hybrid BM25 + vector retrieval, cross-encoder reranking
- Incremental indexing with content-hash caching
- A/B measurement: Layer 1 vs Layer 1+2 quality

**Exit criteria:** Measurable improvement in review quality over Layer 1 baseline.

### Phase 5: Specialization & Distribution (Weeks 17-20)

- Evidence-based decision on specialized agents
- If warranted: Security Agent, Architecture Agent
- GitHub Action distribution
- Feedback collection mechanism (accept/reject signals)
- Governance dashboard (if customer demand exists)

**Exit criteria:** Evidence-based agent roster. Two distribution channels. Feedback data flowing.

---

## 8. Infrastructure and Cost Projections

### MVP Infrastructure

| Component | Monthly Cost |
|---|---|
| Webhook server (single container, 1 vCPU, 1GB) | $20-50 |
| Task queue (Redis or in-process) | $0-15 |
| Monitoring (structured logging) | $0-30 |
| **Total** | **$20-95** |

### Post-MVP Additions (Layer 2)

| Component | Monthly Cost |
|---|---|
| Vector database (LanceDB → Qdrant) | $0-100 |
| Embedding service (Voyage AI) | $0.06-0.12/1M tokens |
| Storage (embedding cache) | $5-20 |
| Background workers (indexing) | $30-100 |
| **Total additions** | **$35-320** |

### LLM Cost per Review (Claude Sonnet 4.5)

| PR Size | Cost (no caching) | Cost (with prompt caching) |
|---|---|---|
| Small (1-5 files) | $0.14 | $0.06 |
| Typical (5-15 files) | $0.32 | $0.12 |
| Large (15-50 files, multi-patch) | $1.28 | $0.45 |

---

## 9. Risk Assessment

### Risks We Accept

| Risk | Likelihood | Impact | Acceptance Rationale |
|---|---|---|---|
| Prompt engineering takes longer than budgeted | High | Medium | Empirical work, not architecture. Schedule for it. |
| Layer 1 quality gap vs competitors | High | Medium | Ships fast; Layer 2 fast follow closes the gap. |
| Python-TypeScript friction for GitHub ecosystem | Medium | Low | TypeScript wrappers post-MVP. Core stays Python. |

### Risks We Mitigate

| Risk | Mitigation |
|---|---|
| FP rate above target | Two-pass review + severity ranking + feedback collection from day one |
| LLM API reliability | Cross-provider fallback (Claude → GPT-4o). Retry with backoff. |
| LlamaIndex instability | Insulation layer + version pinning + Haystack migration target |
| GitHub rate limits | Pending review pattern, Check Run annotations, debouncing |
| IP risk from studying PR-Agent | Clean-room reimplementation. Patterns only, no code. |

### Risks We Avoid

| Risk | How |
|---|---|
| AGPL contamination | Build from scratch. No fork. |
| Over-engineering | Single process, single agent, single platform for MVP. |
| Premature scaling | One container handles hundreds of PRs/day. Scale when needed. |
| Feature bloat | `/review` only until core quality is proven. |

---

## 10. What Makes This "Pragmatic"

This architecture earns the "pragmatic" label because it makes the **least risky bet at every decision point:**

- We build from scratch because AGPL leaves no alternative — not because we think we can build something better than years of PR-Agent iteration on day one.
- We use Python because the LLM ecosystem demands it — not because it's the ideal language for every component of the system.
- We ship with Layer 1 context because it's free and fast — not because we believe heuristics alone produce competitive reviews.
- We start with one agent because single-agent quality is the prerequisite for multi-agent value — not because we doubt multi-agent specialization.
- We target <10% FP because it's achievable with known techniques — not because <5% is impossible.

Every component exists because it solves a problem we have today, not a problem we might have tomorrow. The architecture is designed to be extended — Layer 2 context, specialized agents, governance features — but nothing is built until the evidence demands it.

The result: a system that ships in 12 weeks, works on day one, and can be incrementally improved based on real-world data rather than architectural speculation.

---

## Sources

This architecture synthesizes findings from:
- Competitive analysis (DEM-105): Market positioning, pricing, feature gaps
- PR-Agent deep-dive (DEM-106): Architecture patterns, diff processing, prompt engineering, AGPL finding
- GitHub integration (DEM-107): App vs Action, rate limits, API patterns
- Context/RAG strategies (DEM-108): Embedding approaches, chunking, retrieval pipelines
- Differentiation (DEM-109): Market gaps, positioning options, governance opportunity
- Technical feasibility (DEM-110): Build vs fork, MVP scope, timeline, cost projections
- Retrieval framework evaluation (DEM-114): LlamaIndex recommendation, 10-framework comparison, graph-RAG category mismatch
