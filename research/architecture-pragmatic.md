# Architecture Proposal: Pragmatic — Best Possible Given Current Knowledge

**Date:** 2026-03-23
**Author:** Chief Architect
**Issue:** DEM-118
**Parent:** DEM-117
**Lens:** Pragmatic — proven patterns, established tools, realistic implementation paths, high confidence of success

---

## Executive Summary

Kenjutsu is an AI-powered code review system positioned as **high-signal, governance-aware, and multi-agent-native**. This proposal defines the architecture that gives us the highest probability of shipping a useful product based on everything we know today. Every choice here favors proven technology, well-understood patterns, and incremental buildability over novelty.

The core insight from our research: **context depth is the primary quality differentiator** (82% vs 44% bug detection), but **false positive rate is the primary adoption gate**. This architecture resolves that tension through a layered context pipeline that starts cheap and goes deep only when warranted, combined with a self-reflection pass that filters findings before they reach the developer.

**Key decisions:**
1. Build from scratch (hybrid study approach) — AGPL kills the PR-Agent fork path
2. Python stack with FastAPI — best LLM ecosystem, fastest path to MVP
3. GitHub App as primary integration — rate limits, Checks API, bot identity
4. Layered context pipeline — cheap heuristics always, semantic retrieval when needed
5. Self-reflection scoring for false positive suppression
6. Paperclip-native multi-agent orchestration as the long-term differentiator

---

## 1. System Architecture

### High-Level Data Flow

```
                         ┌─────────────────────────────┐
                         │       GitHub / GitLab        │
                         │    (PR events, webhooks)     │
                         └──────────┬──────────────────-┘
                                    │ webhook POST
                                    ▼
                         ┌──────────────────────┐
                         │    Webhook Server     │
                         │  (FastAPI + HMAC)     │
                         │  Signature verify     │
                         │  Event routing        │
                         │  Ack < 1s, enqueue    │
                         └──────────┬────────────┘
                                    │ async task
                                    ▼
                         ┌──────────────────────┐
                         │   PR Processor        │
                         │  Diff fetching        │
                         │  Token budgeting      │
                         │  Hunk extension       │
                         │  Chunking             │
                         └──────────┬────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │  Context Retriever    │
                         │  L1: Heuristics       │◄── always (free)
                         │  L2: Semantic search  │◄── when needed
                         │  L3: Agentic search   │◄── complex PRs only
                         └──────────┬────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Review Engine       │
                         │  Prompt rendering     │
                         │  LLM call + fallback  │
                         │  Response parsing     │
                         │  Self-reflection pass  │
                         │  Severity scoring     │
                         └──────────┬────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    Publisher          │
                         │  Pending review →     │
                         │    submit atomically  │
                         │  Check Run annotations│
                         │  Persistent comments  │
                         └──────────┬────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   GitHub / GitLab     │
                         │  (PR review, checks)  │
                         └──────────────────────-┘
```

### Design Principles

1. **Precision over recall.** Better to surface 5 high-confidence findings than 20 noisy ones. The cAST research confirms: higher precision correlates with better outcomes more than recall.
2. **Cheap first, expensive when justified.** Every PR gets free heuristic context. Semantic search activates only when the diff touches shared code, APIs, or cross-cutting concerns.
3. **Fail gracefully, never silently.** If context retrieval fails, review proceeds with reduced context — not a crash. If the LLM call fails, the fallback chain engages. If everything fails, a clear error comment is posted on the PR.
4. **Batch and buffer.** GitHub's content creation rate limit (80/min, 500/hr) is the binding constraint. All output flows through the pending review pattern: accumulate all comments, submit once.
5. **Stateless processing, stateful indexing.** Each review is a self-contained pipeline invocation. The codebase index (post-MVP) is the only persistent state.

---

## 2. Component Architecture

### 2.1 Webhook Server

**Technology:** FastAPI (async, high-performance)

**Responsibilities:**
- Receive GitHub/GitLab webhook POST events
- HMAC-SHA256 signature verification (mandatory from day one — PR-Agent's CVEs demonstrate the consequences of skipping this)
- Event routing: `pull_request` (opened, synchronize, reopened), `issue_comment` (slash commands)
- Immediate acknowledgment (< 1 second) with async background dispatch
- Health check and readiness endpoints
- Request-scoped configuration (no global state — explicit config injection, not Dynaconf)

**Key decision: No global state.** PR-Agent's 200+ `get_settings()` call sites create hidden coupling that resists modification. Kenjutsu passes configuration explicitly through the pipeline via dependency injection. Every function declares what it needs.

**Estimated complexity:** 500-800 lines.

### 2.2 Git Platform Provider

**Technology:** PyGithub for GitHub REST API, or direct httpx for lightweight calls. Abstract interface for future GitLab/Bitbucket support.

**Interface design:** A clean `GitProvider` abstract base class with consistent return types. PR-Agent's provider interface has inconsistent signatures across implementations (documented in their issue #2259). We design this correctly from the start:

```
GitProvider (ABC)
├── get_pr_metadata() → PRMetadata
├── get_diff_files() → list[FilePatch]
├── get_file_content(path, ref) → str
├── create_review(comments, body, event) → ReviewResult
├── create_check_run(annotations, summary) → CheckResult
├── get_pr_comments() → list[Comment]
└── add_reaction(comment_id, reaction) → None
```

**GitHub App authentication flow:**
1. Register GitHub App with minimum permissions: `pull_requests: write`, `checks: write`, `contents: read`, `metadata: read`
2. JWT generation (RS256, 10-min lifetime) → installation token exchange (1-hour expiry)
3. Proactive token refresh before expiry
4. Scoped tokens (narrowed to specific repos when possible)

**Rate limit strategy:**
- Monitor `x-ratelimit-remaining` headers on every response
- Throttle proactively when approaching limits
- Batch all review comments into a single pending review → submit
- Use Check Run annotations (50 per API call) for high-volume findings
- Debounce on `synchronize` events: wait 30-60 seconds before starting review (more commits may follow)

**Estimated complexity:** 1,000-1,500 lines.

### 2.3 Diff Processor

**Technology:** Custom parser + tree-sitter (py-tree-sitter) for AST-aware context extension

**Responsibilities:**
- Parse unified diff into structured `FilePatch` objects
- Convert to decoupled hunk format (separate new/old views with line numbers) — this format, proven by PR-Agent, helps the LLM reason about change positioning
- Dynamic context extension: extend hunks to enclosing function/class boundaries via tree-sitter AST queries
- Token-aware chunking: greedy fill within budget, language-prioritized ordering (main language first)
- Large diff strategies:
  - **Clip** (default): truncate individual large patches at function boundaries
  - **Multi-patch**: split into multiple chunks, each gets a separate LLM call (up to 3 parallel)
  - **Summary fallback**: files that don't fit listed by name only
- Deletion omission: strip deletion-only hunks, list deleted files by name
- Token counting via tiktoken (OpenAI-compatible models) and Anthropic token counting API (Claude models)

**Key decision: Function-level chunking via AST.** Research shows function-level isolation scores 0.768 similarity vs 0.739 for full file with the correct function buried in noise. A 7% improvement in retrieval quality is significant at scale. Each chunk includes the class header + imports for context.

**Key decision: No 32K default cap.** PR-Agent's `max_model_tokens = 32000` default means most deployments use a fraction of available context. Kenjutsu reads the actual model context window and uses it, with a configurable safety margin.

**Estimated complexity:** 1,500-2,000 lines. This is core algorithmic work.

### 2.4 Context Retriever

The layered context pipeline is Kenjutsu's most important architectural decision. It resolves the tension between context depth (needed for quality) and noise/cost (the adoption killer).

#### Layer 1 — Always On (Free)

Available from MVP. These are heuristic, deterministic, and cost nothing:

| Signal | Method | What It Finds |
|---|---|---|
| Diff extension | tree-sitter AST queries | Enclosing function/class for each changed hunk |
| Import graph | tree-sitter + static analysis | Direct dependencies of changed files |
| Co-change analysis | `git log` mining | Files that historically change together |
| Test matching | Path heuristics (`*_test.go` ↔ `*.go`) | Related test files |
| Type definitions | Import graph + AST | Type/interface definitions used by changed code |

**Inflection point:** For PRs touching 1-3 files in well-structured codebases, Layer 1 alone may be sufficient. The system should measure and report when it believes deeper context would improve review quality.

#### Layer 2 — On Demand (Medium Cost)

Post-MVP. Activates when the diff touches shared libraries, APIs, or cross-cutting concerns:

| Signal | Method | What It Finds |
|---|---|---|
| Semantic search | Voyage-code-3 embeddings (1024 dims) + BM25 hybrid | Semantically related code across the codebase |
| Reranking | Cross-encoder (ms-marco-MiniLM or Cohere Rerank v3) | Top 10 most relevant chunks from 50-100 candidates |
| Historical reviews | Embedding search on past review comments | Relevant precedent decisions |

**Embedding strategy:**
- Embed natural language descriptions of code, not raw code (Greptile's 12% retrieval improvement is too significant to ignore)
- Tree-sitter AST → function-level chunks → LLM generates natural language summary → Voyage-code-3 embeds the summary
- Hierarchical indexing: summary tier (file/module) for coarse filtering, detail tier (function) for precise retrieval
- Incremental indexing: hash each chunk's content, re-embed only changed chunks (Cursor's Merkle tree approach achieves 90%+ cost reduction)

**Retrieval formula:** Hybrid BM25 + vector, weighted 0.3 keyword / 0.7 vector (adjustable). Code may benefit from higher keyword weight due to identifier significance. Retrieve 50-100 candidates, rerank to top 10 via cross-encoder.

**Key decision: Voyage-code-3 at 1024 dimensions.** Achieves 92.28% of full 2048-dim performance while outperforming OpenAI text-embedding-3-large at 3072 dims. Better quality at 1/3 the storage. Binary quantization available for 32x additional storage reduction.

#### Layer 3 — Complex PRs Only (Higher Cost)

Future. For architectural changes, unfamiliar codebases, and PRs flagged as high-complexity:

| Signal | Method | What It Finds |
|---|---|---|
| Multi-hop dependency tracing | Agentic search (LLM-guided graph traversal) | Transitive dependencies, indirect impacts |
| Pattern matching | AST-grep with YAML rules | Security patterns, API misuse, resource management violations |
| Cross-service analysis | Multi-repo index queries | Impact on dependent services |

#### Context Decision Logic

```
For each PR:
  1. Always run Layer 1 (free, < 2 seconds)
  2. Score PR complexity:
     - Files changed > 5, OR
     - Touches shared library / API / interface, OR
     - Cross-directory changes, OR
     - Layer 1 context insufficient (few imports, no co-changes)
  3. If complexity score > threshold → activate Layer 2
  4. If PR touches security-sensitive code OR is flagged for deep review → activate Layer 3
```

### 2.5 Review Engine

**Technology:** Jinja2 templates, Pydantic for structured output schemas, LiteLLM for multi-provider support

**Two-pass review architecture:**

**Pass 1 — Generate findings:**
- Render Jinja2 prompt template with: system instructions, diff (decoupled hunk format), retrieved context, configuration rules
- LLM call via LiteLLM (primary: Claude Sonnet 4.5, fallback: GPT-4o)
- Parse structured response (YAML/JSON with Pydantic validation)
- Each finding includes: file, line range, severity (critical/warning/info), category, description, suggested fix (optional), confidence score

**Pass 2 — Self-reflection (false positive filter):**
- Second LLM call scores each finding 0-10 on: correctness, relevance, actionability
- Validates line number accuracy against the actual diff
- Filters findings below configurable threshold (default: score >= 7)
- Findings scoring >= 9 marked as "high confidence"

**Key decision: Self-reflection is non-negotiable.** PR-Agent's `/improve` tool uses this pattern (generate → score → filter) and it measurably reduces noise. The second call is cheaper (smaller context: just findings + relevant diff chunks) and worth the latency.

**Prompt engineering strategy:**
- Study PR-Agent's prompt structures (structured output approach, Pydantic models in prompts, YAML format) — techniques are not copyrightable
- Jinja2 templates allow conditional sections based on context availability
- Separate prompt templates per review focus: general, security, performance, architecture
- Prompt caching (Claude and OpenAI both support this) reduces input costs up to 90% for repeated system prompts — critical for cost control

**Token budget allocation:**

| Segment | Budget % | Notes |
|---|---|---|
| System prompt + instructions | 5% | Prompt-cached across reviews |
| Retrieved context (Layer 1+2) | 30% | Reranked top-k from hybrid search |
| Diff (formatted) | 50% | The actual PR changes with context extension |
| Output buffer | 15% | Generation headroom |

**Model selection:**
- **Standard review:** Claude Sonnet 4.5 ($0.22-0.35 per typical PR). Best cost/quality ratio. 200K context window.
- **Self-reflection pass:** Same model or cheaper. Scoring findings doesn't need frontier reasoning.
- **Complex PR deep review:** Claude Opus 4.6 ($1.10-1.75 per typical PR). Reserved for high-complexity PRs or security-critical code.
- **Fallback:** GPT-4o. Different model family reduces correlated failures.

**Estimated complexity:** 1,500-2,000 lines. Prompt engineering iteration is the long pole.

### 2.6 Publisher

**Technology:** GitHub REST API via the Git Platform Provider abstraction

**Publishing strategy — the pending review pattern:**
1. Create a `PENDING` review (invisible to PR author)
2. Accumulate all inline comments into the review
3. Submit atomically with a summary body and `COMMENT` event
4. Result: one notification to the PR author, not N

**Output format:**
- Summary comment with severity breakdown (X critical, Y warning, Z info)
- Inline comments on specific lines with severity badges
- Suggestion blocks (```suggestion) for one-click apply where appropriate
- Check Run with annotations for status integration (pass/fail in branch protection)

**Severity presentation:**
- **Critical** — likely bugs, security vulnerabilities, data loss risks. Always shown.
- **Warning** — code quality issues, potential performance problems, missing error handling. Shown by default, configurable.
- **Info** — style suggestions, minor improvements. Hidden by default, configurable.

**Key decision: Silent by default.** Kenjutsu only comments on genuine issues. Style nitpicking, formatting suggestions, and low-confidence findings are suppressed unless the team explicitly enables them. This is the single most important UX decision for adoption.

**Estimated complexity:** 600-1,000 lines.

### 2.7 Configuration System

**Technology:** TOML (`.kenjutsu.toml` in repo root)

**Design:**
- Sensible zero-config defaults (review works immediately on install)
- Per-tool settings: review strictness, severity thresholds, model selection
- File/directory ignore patterns (glob + regex)
- Team-specific rules: custom review guidelines, domain conventions
- Explicit configuration injection — no global state, no Dynaconf

**Priority order (lowest → highest):**
1. Built-in defaults
2. Organization-level config (via GitHub App settings)
3. Repository `.kenjutsu.toml`
4. PR-level overrides (slash commands in PR comments)

**Estimated complexity:** 400-600 lines.

---

## 3. Paperclip Integration (Multi-Agent Orchestration)

This is Kenjutsu's long-term structural differentiator. No competitor has an agent orchestration platform.

### Multi-Agent Review Architecture

```
PR Event
    │
    ▼
┌──────────────┐
│  Coordinator │  Paperclip agent: routes PR to specialist agents
│  Agent       │  based on file types, directories, and review focus
└──────┬───────┘
       │ parallel dispatch
       ├──────────────────┐──────────────────┐
       ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Security    │  │ Performance  │  │ Architecture │
│  Reviewer    │  │ Reviewer     │  │ Reviewer     │
│  (Agent)     │  │ (Agent)      │  │ (Agent)      │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                  │                  │
       └──────────┬───────┘──────────────────┘
                  ▼
          ┌──────────────┐
          │  Aggregator  │  Deduplicates, resolves conflicts,
          │  Agent       │  applies severity ranking, publishes
          └──────────────┘
```

**What this enables:**
- **Specialized focus reduces false positives.** A security agent trained on OWASP patterns produces fewer irrelevant style suggestions. A performance agent doesn't comment on naming conventions.
- **Agent provenance.** Every finding is attributable to a specific agent. Audit trail built in.
- **Composable pipelines.** Teams configure which agents review which file types/directories. Backend team gets performance + architecture review. Frontend team gets accessibility + security review.
- **Disagreement resolution.** When agents conflict, escalation follows Paperclip's chain of command.
- **Budget-aware processing.** Paperclip's budget tracking prevents unbounded LLM costs. Complex PRs get more agents; simple PRs get fewer.
- **Independent learning.** Each agent's feedback loop (accepted/rejected suggestions) improves that specialization independently.

**MVP approach:** Single generalist review agent. Multi-agent orchestration layers on post-MVP without changing the core pipeline — each specialist agent runs the same review engine with different prompt templates and configuration.

### Governance Layer

Paperclip integration enables governance capabilities no competitor offers:

- **Agent provenance tracking:** Every review decision records which agent made it, which model was used, and what context was available
- **Proportional approval workflows:** Higher-risk code (security-sensitive, data-handling, infrastructure) triggers stricter review requirements
- **Compliance audit trails:** Full record of who generated code, who (human or agent) reviewed it, confidence levels, and approval chain
- **Trust scoring:** PRs from AI coding agents (Cursor, Claude Code, Copilot) flagged for proportional scrutiny

**Regulatory relevance:** EU AI Act (August 2026) and Colorado AI Act (June 2026) create regulatory demand for AI-generated code governance. This positioning is unoccupied.

---

## 4. Technology Choices

### Language: Python

**Rationale:**
- Best LLM ecosystem: LiteLLM, tiktoken, Anthropic SDK, OpenAI SDK
- Tree-sitter bindings (py-tree-sitter) production-ready
- FastAPI for async webhook server
- PR-Agent (studied, not forked) is Python — learnings transfer directly
- Fastest path to MVP

**Alternative considered:** TypeScript. Closer to GitHub/VS Code ecosystem. Better for future IDE extensions. Weaker LLM library ecosystem and tree-sitter support. Revisit for IDE components post-MVP.

### Key Dependencies

| Library | Purpose | Rationale |
|---|---|---|
| FastAPI | Webhook server | Async, high-performance, well-documented |
| LiteLLM | Multi-LLM provider | 100+ providers, unified interface, handles model quirks |
| tiktoken | Token counting | OpenAI-compatible, fast |
| py-tree-sitter | AST parsing | Universal parser, production-proven (Neovim, Helix, Zed) |
| PyGithub | GitHub API | Mature, well-maintained |
| Jinja2 | Prompt templates | Flexible, conditional rendering |
| Pydantic | Structured output schemas | Type validation, JSON schema generation |
| httpx | HTTP client | Async, modern, for direct API calls |

### What We Explicitly Avoid

| Anti-Pattern | Why | Alternative |
|---|---|---|
| Dynaconf / global settings | 200+ `get_settings()` in PR-Agent = hidden coupling | Explicit config injection |
| Monolithic dependencies | PR-Agent installs 35 deps regardless of provider | Optional extras: `kenjutsu[github]`, `kenjutsu[gitlab]` |
| Hardcoded command registry | PR-Agent's `command2class` dict blocks extensibility | Plugin system with registration |
| 32K token default cap | PR-Agent wastes most of modern context windows | Actual model limits with configurable margin |
| YAML-only LLM output | Fragile parsing with extensive repair logic | Structured output (function calling) where available, JSON with YAML fallback |

---

## 5. Build vs Fork Decision

### Why We Build From Scratch

| Factor | Assessment |
|---|---|
| **AGPL license** | PR-Agent changed from Apache 2.0 to AGPL-3.0 in May 2025. Running a modified fork as a service requires making all source code available. This eliminates commercial SaaS on a current fork. |
| **v0.29 (last Apache)** | Saves 4-6 weeks but inherits: 200+ global state call sites, 1.5K-line god files, 43 bare except clauses, mandatory dependency bloat. Full refactoring sprint needed within first quarter. |
| **Architecture quality** | Building clean gives us: proper dependency injection, plugin system, consistent provider interfaces, no technical debt from day one. |
| **Differentiation** | A fork constrains us to PR-Agent's single-pass, diff-only, stateless architecture. Our differentiation (layered context, multi-agent, governance) requires fundamentally different foundations. |

### What We Study (Legally Safe)

1. **Prompt engineering strategies** — structured output, Pydantic models in prompts, self-reflection scoring. Techniques are not copyrightable.
2. **Diff processing algorithms** — token-aware chunking, dynamic context expansion, decoupled hunk format. Algorithmic ideas, independently reimplemented.
3. **Configuration schema** — PR-Agent's `configuration.toml` is a comprehensive feature checklist.
4. **Provider interface design** — what operations a code review tool needs (then design cleaner).

---

## 6. Data Flow: End-to-End PR Review

### Happy Path (Typical PR: 10 files, 500 lines)

```
T+0s     GitHub sends pull_request webhook (opened/synchronize)
T+0.1s   Webhook server: HMAC verify → ack 200 → enqueue async task
T+0.5s   PR Processor: fetch PR metadata, diff, file list
T+1.5s   Diff Processor: parse unified diff → decoupled hunks → context extension via tree-sitter
T+2.0s   Context Retriever L1: import graph + co-change + test matching
T+2.5s   Token budgeting: allocate diff + context within model limits
T+3.0s   Review Engine Pass 1: render prompt → LLM call (Claude Sonnet 4.5)
T+18s    Response parsing: extract findings, validate structure
T+18.5s  Review Engine Pass 2: self-reflection scoring → filter FPs
T+28s    Publisher: format findings → pending review → submit atomically
T+29s    Publisher: create Check Run with annotation summary
T+30s    Done. Developer sees one review with severity-ranked findings.
```

**Total latency: ~30 seconds.** Comparable to PR-Agent's single-call design, but with context and FP filtering.

### Large PR Path (50+ files, 2000+ lines)

```
T+0-3s    Same as above through diff processing
T+3s      Multi-patch split: 3-4 chunks within token budget
T+3-25s   Parallel LLM calls (one per chunk) + Layer 2 context if activated
T+25-35s  Aggregate findings across chunks
T+35-45s  Self-reflection pass on aggregated findings
T+45-50s  Publish
```

**Total latency: ~50-60 seconds.** Parallel processing keeps large PRs manageable.

### Incremental Review (New Commits on Existing PR)

```
T+0s     synchronize webhook → debounce 30-60 seconds
T+30-60s Diff new commits against last reviewed commit (not full PR)
         → normal pipeline on delta only
         → dismiss stale findings that no longer apply
```

---

## 7. Trade-offs and Risks

### Deliberate Trade-offs

| We Choose | Over | Because |
|---|---|---|
| Precision (< 5% FP) | Recall (catch every bug) | False positives are the #1 adoption killer. A tool that speaks only when it matters earns trust. |
| Build from scratch | Fork for speed | AGPL blocks commercial use. Technical debt from forking costs more long-term than building clean. |
| Python | TypeScript | LLM ecosystem maturity. We can add TS for IDE components later. |
| GitHub App first | Multi-platform from day one | GitHub is the dominant platform. Ship one integration well before spreading thin. |
| Single agent MVP | Multi-agent from day one | Prove the core review quality first. Multi-agent is additive — same engine, different prompts. |
| Heuristic context first | Full embeddings from day one | Layer 1 context is free and fast. Embeddings add cost and complexity. Layer 1 is sufficient for many PRs. |

### Known Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **FP rate > 5% target** | High | Critical | Self-reflection pass. Budget 3-4 weeks for prompt tuning on real PRs. Feedback loop post-MVP. |
| **Prompt engineering iteration** | High | High | Start with PR-Agent's strategies. Iterate empirically. This is the long pole — schedule for it. |
| **Large diff edge cases** | Medium | Medium | Multi-patch mode, token budget management. Test against real-world monorepo commits. |
| **GitHub rate limits** | Medium | Medium | Pending review pattern, Check Run annotations, debouncing. Monitor headers proactively. |
| **Context noise hurting quality** | Medium | High | Layered retrieval with explicit quality gates. Reranking to top-k only. Measure retrieval precision. |
| **Market timing** | Medium | High | Governance niche is still open. EU AI Act deadline creates urgency. Ship before August 2026. |

---

## 8. MVP Scope

### In Scope (MVP)

| Component | Detail |
|---|---|
| GitHub App | Webhook server, app authentication, bot identity |
| `/review` command | Structured review with severity ranking |
| Layer 1 context | Heuristics: import graph, co-change, test matching, diff extension |
| Self-reflection | FP filtering via second LLM pass |
| Configuration | `.kenjutsu.toml` with sensible defaults |
| Check Runs | Summary status with line-level annotations |
| Inline suggestions | `suggestion` blocks for one-click apply |
| CLI | Local testing without GitHub App infrastructure |
| Single LLM provider | Claude Sonnet 4.5 (primary) |

### Out of Scope (Post-MVP)

| Component | Phase |
|---|---|
| Layer 2 context (embeddings, semantic search) | Phase 2 (weeks 13-16) |
| Multi-agent review (security, performance, architecture specialists) | Phase 3 |
| GitLab / Bitbucket / Azure DevOps | Phase 3 |
| `/describe`, `/improve`, `/ask` commands | Phase 2 |
| Feedback loop learning (upvote/downvote → embeddings) | Phase 3 |
| Governance audit trails | Phase 3 |
| GitHub Action distribution | Phase 2 |
| Web UI for configuration | Phase 4 |
| Knowledge preservation (institutional decision memory) | Phase 4 |

---

## 9. Cost Model

### Per-PR Costs (MVP, Claude Sonnet 4.5)

| PR Size | LLM Calls | Input Tokens | Output Tokens | Cost |
|---|---|---|---|---|
| Small (3 files, 100 lines) | 2 (review + reflect) | ~30K | ~3K | $0.14 |
| Typical (10 files, 500 lines) | 2 | ~65K | ~8K | $0.32 |
| Large (50 files, 2000 lines) | 5 (3 chunk + 1 aggregate + 1 reflect) | ~300K | ~25K | $1.28 |

**With prompt caching (90% reduction on system prompt):** Costs decrease 15-25% for the cached portion.

### Infrastructure Costs (MVP)

| Component | Monthly Cost |
|---|---|
| Webhook server (single container) | $20-50 |
| Task queue (Redis or in-process) | $0-15 |
| Monitoring (structured logging) | $0-30 |
| **Total** | **$20-95** |

### Break-Even

At $24/seat/month (market price point) and $0.32 average cost per PR, a developer generating 3 PRs/day costs ~$20/month in LLM usage. Break-even at approximately 4 PRs/seat/month (achievable for any active developer).

---

## 10. Competitive Positioning

Based on our research, Kenjutsu occupies a position no current tool holds:

| Dimension | CodeRabbit | Greptile | PR-Agent | **Kenjutsu** |
|---|---|---|---|---|
| Signal quality | Medium (noisy) | High (but FPs) | Low (shallow) | **High (precision-first)** |
| Context depth | Medium (AST-grep + RAG) | High (full index) | Low (diff-only) | **Layered (adaptive)** |
| Governance | None | None | None | **Paperclip-native** |
| Multi-agent | No | No | No (Qodo 2.0 gated) | **Yes (orchestrated)** |
| Self-hosted | Docker (enterprise) | Enterprise only | Yes (AGPL) | **Yes (clean license)** |
| Pricing model | $24/seat | $30/seat | Free + paid | **$24/seat (competitive)** |

**The pitch:** "The code review tool that speaks only when it matters, with governance built in."

---

## Sources

This architecture synthesizes findings from:
- Competitive analysis (`research/competitive-analysis.md`)
- Context and RAG strategies (`research/context-rag-strategies.md`)
- Differentiation opportunities (`research/differentiation.md`)
- GitHub integration options (`research/github-integration.md`)
- PR-Agent deep-dive (`research/pr-agent-deep-dive.md`)
- Technical feasibility assessment (`research/technical-feasibility.md`)
