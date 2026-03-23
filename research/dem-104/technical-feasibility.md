# Technical Feasibility: MVP Architecture, Build vs Fork, Infrastructure

- **Status:** review
- **Author:** Chief Architect
- **Date:** 2026-03-23
- **Issue:** DEM-110
- **Parent:** DEM-104

---

## Executive Summary

Building an AI-powered code review tool is technically feasible. The recommended path is **build from scratch with a hybrid approach** (study PR-Agent's architecture and prompts, implement clean). The MVP requires a GitHub App webhook server, a diff processing pipeline, a context retrieval layer, LLM integration, and a review publishing system. Estimated MVP complexity: **10-14 weeks** for a team of 2-3 engineers, producing a functional GitHub App that reviews PRs with codebase-aware context. The primary technical risk is prompt engineering iteration — getting false positive rates below 5% requires empirical tuning, not just architecture.

---

## 1. Build vs Fork Decision

### Decision Framework

| Criterion | Weight | Fork (AGPL) | Fork v0.29 (Apache) | Build + Study | Score |
|---|---|---|---|---|---|
| Commercial viability | Critical | Blocked (AGPL) | Yes | Yes | Fork AGPL eliminated |
| Architecture quality | High | Poor (global state) | Poor (global state) | Excellent | Build wins |
| Time to first PR review | Medium | 2-4 weeks | 4-6 weeks | 8-10 weeks | Fork faster |
| Long-term maintainability | High | Low | Low-Medium | High | Build wins |
| Legal risk | Critical | High (viral clause) | Low (attribution) | None | Build safest |
| Upstream improvements | Low | Available (AGPL only) | Frozen May 2025 | N/A | Irrelevant |
| Differentiation potential | High | Constrained by architecture | Constrained | Unlimited | Build wins |

### Recommendation: Build from Scratch (Hybrid Approach)

**The AGPL license change eliminates forking current PR-Agent for a commercial product.** Forking v0.29 (last Apache 2.0) saves 4-6 weeks but inherits architectural debt (200+ global state call sites, 1.5K-line god files, 43 bare except clauses, mandatory bloated dependencies) that would require a full refactoring sprint within the first quarter anyway.

**Study PR-Agent, build clean:**
- Borrow prompt engineering *strategies* (not code) — structured YAML output, Pydantic schema definitions, self-reflection scoring
- Reimplement diff processing *algorithms* — token-aware chunking, dynamic context extension, decoupled hunk format
- Use PR-Agent's `configuration.toml` as a feature checklist for configuration design
- Design a proper plugin system and dependency injection from day one

---

## 2. Minimum Viable Architecture

### System Overview

```
GitHub Webhook Event
       │
       ▼
┌──────────────┐
│ Webhook      │  FastAPI/Starlette server
│ Server       │  HMAC-SHA256 verification
│              │  Event routing
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ PR Processor │  Diff fetching, file retrieval
│              │  Token budget management
│              │  Hunk extension & chunking
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Context      │  Layer 1: Heuristics (imports, co-change, test matching)
│ Retriever    │  Layer 2: Semantic search (embeddings + BM25)
│              │  Layer 3: Reranking (cross-encoder)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Review       │  Prompt rendering (Jinja2 + structured output)
│ Engine       │  LLM call (with fallback chain)
│              │  Response parsing & validation
│              │  Severity scoring & false positive filtering
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Publisher     │  PR Review API (pending → submit pattern)
│              │  Check Runs (annotations)
│              │  Persistent comment management
└──────────────┘
```

### MVP Components

#### Component 1: Webhook Server
- FastAPI server receiving GitHub webhook POST events
- HMAC-SHA256 signature verification
- Event routing: `pull_request` (opened, synchronize, reopened), `issue_comment`
- Background task dispatch for PR processing
- Health check endpoint
- **Complexity:** Low. 500-800 lines.

#### Component 2: GitHub Provider
- GitHub App authentication (JWT → installation token, 1-hour refresh)
- PR metadata fetching (title, description, commits, files, diff)
- File content retrieval (for context beyond diff)
- Review publishing (pending review → comment accumulation → atomic submit)
- Check Run creation (annotations for summary status)
- Rate limit monitoring and throttling
- **Complexity:** Medium. 1,000-1,500 lines. PyGithub or direct REST.

#### Component 3: Diff Processor
- Parse unified diff into structured patch objects
- Convert to decoupled hunk format (new/old views with line numbers)
- Dynamic context extension (extend hunks to enclosing function/class via tree-sitter)
- Token-aware chunking (greedy fill within budget, language-prioritized ordering)
- Large diff strategies: clip, skip, multi-patch
- Deletion omission (strip deletion-only hunks, list deleted files by name)
- **Complexity:** High. 1,500-2,000 lines. Core algorithmic work.

#### Component 4: Context Retriever (MVP: Layer 1 only)
- **Layer 1 (MVP):** Import graph traversal via tree-sitter, co-change analysis from git log, test file matching via path heuristics, enclosing function/class extraction
- **Layer 2 (post-MVP):** Function-level embeddings (Voyage-code-3), hybrid BM25 + vector search, incremental indexing with content-hash caching
- **Layer 3 (post-MVP):** Cross-encoder reranking, historical review matching
- **MVP Complexity:** Medium. 800-1,200 lines for Layer 1.

#### Component 5: Review Engine
- Jinja2 prompt templates with structured output schemas
- LLM integration via LiteLLM (multi-provider support built-in)
- Model-specific handling (temperature, system message, reasoning effort)
- Fallback chain (primary model → fallback models)
- YAML/JSON response parsing with repair logic
- Severity scoring (critical/warning/info)
- Self-reflection pass for false positive filtering (second LLM call scores each finding)
- **Complexity:** High. 1,500-2,000 lines. Prompt engineering is the long pole.

#### Component 6: Configuration System
- TOML-based repo configuration (`.kenjutsu.toml`)
- Sensible defaults for zero-config operation
- Per-tool settings (review strictness, ignored patterns, model selection)
- File/directory ignore patterns (glob + regex)
- **Complexity:** Low. 400-600 lines.

#### Component 7: Publisher
- Pending review pattern (create → accumulate → submit atomically)
- Inline suggestions (```suggestion blocks)
- Check Run creation with annotations (50 per call, batched)
- Persistent comment management (edit existing vs create new)
- Markdown formatting with severity indicators
- **Complexity:** Medium. 600-1,000 lines.

### MVP Scope (What's In / What's Out)

| In (MVP) | Out (Post-MVP) |
|---|---|
| GitHub App integration | GitLab, Bitbucket, Azure DevOps |
| `/review` command (structured review) | `/describe`, `/improve`, `/ask`, `/test` |
| Single-pass review with context | Multi-agent specialized review |
| Layer 1 context (heuristics) | Layer 2-3 context (embeddings, reranking) |
| TOML configuration | Web UI for configuration |
| CLI for local testing | GitHub Action distribution |
| Single LLM provider (Claude) | Multi-provider fallback |
| Severity-ranked findings | Confidence scores, FP rate tracking |
| Self-reflection FP filtering | Feedback loop learning |

---

## 3. LLM Requirements

### Model Capabilities Needed

| Capability | Why | Model Requirement |
|---|---|---|
| Large context window | Fit diff + context + prompt | >= 100K tokens |
| Structured output | Reliable YAML/JSON responses | Function calling or strong instruction following |
| Code understanding | Identify bugs, patterns, security issues | Frontier-class (Claude Opus/Sonnet, GPT-4o+) |
| Reasoning | Cross-file analysis, architectural concerns | Extended thinking / chain-of-thought |
| Low hallucination | False positives are the #1 complaint | Grounded in provided context |

### Token Budget Estimates

For a typical PR (10 files, 500 lines changed):

| Segment | Tokens | % of Budget |
|---|---|---|
| System prompt + review instructions | ~3,000 | 3% |
| Diff (formatted, with context extension) | ~15,000-25,000 | 20-25% |
| Retrieved context (Layer 1 heuristics) | ~10,000-20,000 | 15-20% |
| Retrieved context (Layer 2 embeddings, post-MVP) | ~20,000-30,000 | 20-30% |
| Output buffer | ~5,000-10,000 | 5-10% |
| **Total per review call** | **~50,000-80,000** | — |

For large PRs (50+ files, 2000+ lines):
- Multi-patch mode: 3-4 LLM calls at ~80K tokens each
- Self-reflection pass: 1 additional call at ~20K tokens
- Total: ~260K-340K tokens per large PR review

### Cost Estimates per PR

| Model | Cost per 1M input tokens | Cost per 1M output tokens | Typical PR Cost | Large PR Cost |
|---|---|---|---|---|
| Claude Sonnet 4.5 | $3.00 | $15.00 | $0.22-0.35 | $0.90-1.50 |
| Claude Opus 4.6 | $15.00 | $75.00 | $1.10-1.75 | $4.50-7.50 |
| GPT-4o | $2.50 | $10.00 | $0.18-0.28 | $0.75-1.20 |

**Recommendation:** Use Sonnet-class models for standard review (cost-effective, fast). Reserve Opus-class for self-reflection scoring and complex/large PRs. Prompt caching reduces input costs up to 90% for repeated system prompts.

### Model Selection for MVP

**Primary: Claude Sonnet 4.5** — Best cost/quality ratio. 200K context window. Strong structured output. Good code understanding.

**Self-reflection: Same model or cheaper** — The self-reflection pass (scoring each finding 0-10) doesn't need the most powerful model.

**Fallback: GPT-4o** — Different model family as fallback reduces correlated failures.

---

## 4. Infrastructure Requirements

### MVP Infrastructure

| Component | Requirement | Estimated Cost |
|---|---|---|
| Webhook server | Single container/VM, 1 vCPU, 1GB RAM | $20-50/month |
| Async task queue | Redis or in-process queue (MVP) | $0-15/month |
| Configuration store | Filesystem or SQLite (MVP) | $0 |
| Secrets management | Environment variables (MVP) | $0 |
| Monitoring | Structured logging + error tracking | $0-30/month |
| **Total infrastructure** | | **$20-95/month** |

### Post-MVP Infrastructure (with embeddings)

| Component | Requirement | Estimated Cost |
|---|---|---|
| Vector database | LanceDB (embedded) or Qdrant (hosted) | $0-100/month |
| Embedding service | Voyage AI API | $0.06-0.12 per 1M tokens |
| Persistent storage | S3/GCS for embeddings cache | $5-20/month |
| Background workers | For indexing/re-indexing | $30-100/month |
| **Total post-MVP** | | **$35-320/month** |

### Scaling Considerations

| Scale | PRs/day | Infrastructure | Monthly Infra Cost | Monthly LLM Cost |
|---|---|---|---|---|
| Solo/small team | 5-20 | Single container | $20-50 | $5-25 |
| Mid-size team | 50-200 | 2-3 containers + Redis | $100-200 | $25-150 |
| Enterprise (single org) | 500-2000 | K8s cluster, dedicated DB | $500-1500 | $250-1500 |
| Multi-tenant SaaS | 5000+ | Horizontally scaled cluster | $2000-5000 | $2500-15000 |

### Webhook Processing

GitHub sends webhooks with a 10-second timeout. The server must acknowledge quickly and process asynchronously:
- Accept webhook → validate signature → enqueue task → return 200 (< 1 second)
- Background worker picks up task → processes PR → posts review (30-120 seconds)
- For large PRs with multi-patch processing: up to 5 minutes

---

## 5. Technology Stack Recommendation

### Language: Python

**Rationale:**
- Best LLM ecosystem (LiteLLM, tiktoken, Anthropic SDK, OpenAI SDK)
- Tree-sitter bindings available (py-tree-sitter)
- FastAPI/Starlette for async webhook server
- PyGithub for GitHub API (or httpx for direct REST)
- Fastest path to MVP given the ecosystem
- PR-Agent's architecture (studied, not forked) is Python — learnings transfer directly

**Alternative considered: TypeScript.** Closer to GitHub/VS Code ecosystem. Better for future IDE extensions. But weaker LLM library ecosystem and tree-sitter support. Can revisit for IDE components post-MVP.

### Key Dependencies

| Library | Purpose | Why This One |
|---|---|---|
| FastAPI | Webhook server | Async, high-performance, well-documented |
| LiteLLM | Multi-LLM provider | 100+ providers, unified interface |
| tiktoken | Token counting | OpenAI-compatible, fast |
| py-tree-sitter | AST parsing | Universal parser, production-proven |
| PyGithub | GitHub API | Mature, well-maintained |
| Jinja2 | Prompt templates | Flexible, conditional rendering |
| Pydantic | Structured output schemas | Type validation, JSON schema generation |
| dynaconf or tomli | Configuration | TOML parsing (avoid Dynaconf complexity — use simple TOML loading) |

### What NOT to Use

- **Dynaconf** — PR-Agent's 200+ `get_settings()` pattern creates global state coupling. Use explicit config injection.
- **Monolithic dependency install** — Use optional extras (`pip install kenjutsu[github]`, `pip install kenjutsu[gitlab]`).
- **Hardcoded command registry** — Design a plugin system from day one, even if MVP only has one command.

---

## 6. Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Prompt engineering iteration** | High | High | Budget 3-4 weeks for iterative prompt tuning. This is the long pole. Start with PR-Agent's prompt strategies, iterate on real PRs. |
| **False positive rate > target** | High | Critical | Self-reflection scoring pass. Feedback loop (post-MVP). Aggressive filtering. Design for precision over recall from day one. |
| **Large diff handling edge cases** | Medium | Medium | Multi-patch mode, token budget management. Test against real-world large PRs (1000+ file monorepo commits). |
| **GitHub rate limits** | Medium | Medium | Batch reviews, pending review pattern, Check Run annotations. Monitor rate limit headers proactively. |
| **Tree-sitter language coverage** | Low | Medium | Tree-sitter supports virtually every language. Fallback to regex-based heuristics for unsupported languages. |
| **LLM API reliability** | Medium | Medium | Fallback chain across providers. Retry with exponential backoff. |
| **Context window management** | Medium | High | Rigorous token counting before every LLM call. Graceful degradation (reduce context, not fail). |

### Non-Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Market timing** | Medium | High | Market is active and growing. Early mover advantage diminishing but governance niche is still open. |
| **Benchmark expectations** | High | Medium | Competitors benchmark aggressively. Need internal benchmark suite from day one. |
| **Enterprise sales cycle** | High | Medium | Start with developer-led adoption (free tier / OSS). Enterprise features layer on top. |

---

## 7. Timeline Estimate

### Phase 1: Foundation (Weeks 1-4)

| Week | Deliverable |
|---|---|
| 1 | GitHub App registration, webhook server, signature verification, PR event handling |
| 2 | GitHub provider (auth, diff fetching, file retrieval, review publishing) |
| 3 | Diff processor (parsing, hunk formatting, token budgeting, chunking) |
| 4 | Configuration system, CLI for local testing |

**Milestone:** Can receive a PR webhook, fetch diff, process it, and post a raw diff summary as a PR comment.

### Phase 2: Review Intelligence (Weeks 5-8)

| Week | Deliverable |
|---|---|
| 5 | LLM integration (LiteLLM, prompt templates, structured output parsing) |
| 6 | Review engine (review prompt, YAML parsing, Markdown formatting, severity scoring) |
| 7 | Context Layer 1 (tree-sitter integration, import graph, dynamic hunk extension) |
| 8 | Self-reflection pass (false positive filtering), publisher (pending review pattern, Check Runs) |

**Milestone:** Can review a real PR with context-aware findings, severity ranking, and false positive filtering. Posts as a proper GitHub review with inline comments.

### Phase 3: Polish & Hardening (Weeks 9-12)

| Week | Deliverable |
|---|---|
| 9-10 | Prompt engineering iteration on real PRs (tune for <5% FP rate) |
| 11 | Large PR handling (multi-patch mode), edge cases, error handling |
| 12 | Deployment packaging (Docker), documentation, internal benchmark suite |

**Milestone:** Production-ready MVP that can be installed on real repositories.

### Phase 4: Context Depth (Weeks 13-16, Post-MVP)

| Week | Deliverable |
|---|---|
| 13-14 | Embedding pipeline (Voyage-code-3, function-level chunks, incremental indexing) |
| 15 | Hybrid retrieval (BM25 + vector, cross-encoder reranking) |
| 16 | Integration testing, performance benchmarking |

**Milestone:** Full codebase context during review. Expected to significantly improve bug detection rate.

### Team Size

- **MVP (Phases 1-3):** 2-3 engineers. One focused on infrastructure (webhook server, GitHub provider, deployment). One focused on review intelligence (diff processing, LLM integration, prompts). One focused on context retrieval and testing.
- **Post-MVP (Phase 4+):** Add 1-2 engineers for embedding pipeline, additional platform support, multi-agent orchestration.

---

## 8. Summary Recommendation

| Question | Answer |
|---|---|
| **Is it technically feasible?** | Yes. No novel research required — the problem space is well-understood from PR-Agent and competitors. |
| **Build or fork?** | Build from scratch (hybrid study approach). AGPL kills current fork. v0.29 fork saves weeks but creates months of refactoring debt. |
| **Primary technology risk?** | Prompt engineering iteration. Getting FP rate below 5% is empirical work, not architecture. Budget 3-4 weeks for tuning. |
| **MVP timeline?** | 10-12 weeks with 2-3 engineers. 4 additional weeks for codebase context (embeddings). |
| **MVP monthly cost?** | Infrastructure: $20-95/month. LLM: $5-150/month depending on volume. Total: under $250/month for a small team. |
| **What makes it worth building?** | The governance + multi-agent + precision positioning is unoccupied. Paperclip integration is a unique advantage no competitor can replicate. |

---

## Dependencies on Prior Research

This assessment synthesizes findings from:
- [DEM-106](/DEM/issues/DEM-106): PR-Agent architecture deep-dive → fork vs build data, diff processing algorithms
- [DEM-107](/DEM/issues/DEM-107): GitHub integration options → GitHub App architecture, rate limits, review API
- [DEM-108](/DEM/issues/DEM-108): Context and RAG strategies → embedding approach, chunking, retrieval pipeline
- [DEM-109](/DEM/issues/DEM-109): Differentiation opportunities → MVP scope priorities, positioning requirements
