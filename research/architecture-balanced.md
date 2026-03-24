# Architecture Proposal: Balanced — Pragmatic Innovation

**Date:** 2026-03-24 (v2 — revised per board feedback)
**Author:** Chief Architect
**Issue:** DEM-120
**Parent:** DEM-117

---

## Design Philosophy

This architecture finds the sweet spot between proven approaches and strategic innovation. The guiding principle: **be conservative where failure cost is high, be ambitious where the risk-reward ratio is favorable.**

- **Conservative:** GitHub App integration, Python stack, build-from-scratch IP strategy, diff processing algorithms, webhook infrastructure — these are solved problems with known failure modes. Use proven patterns.
- **Ambitious:** Multi-agent review via Paperclip, natural language code descriptions for retrieval, governance-aware review pipeline, LlamaIndex-orchestrated tiered context — these are differentiation vectors where the upside justifies the engineering investment.

The result is a system that ships a useful MVP quickly using battle-tested infrastructure, while building toward capabilities no competitor can replicate.

---

## Assumptions We Challenge

The research provides a strong foundation, but several claims deserve scrutiny before we build on them. Architecture decisions should survive contact with skepticism.

### 1. "82% vs 44% bug detection means full indexing is non-negotiable"

The Greptile benchmark (DevToolsAcademy Macroscope 2025) is frequently cited but has limitations: it was conducted by a third party using Greptile-adjacent methodology, it is not peer-reviewed, and the 50-PR sample size across 5 repos is small. The 82% figure is for Greptile's full pipeline (AST index + agentic search + feedback loop), not solely for codebase indexing.

**Our position:** Full codebase context clearly helps, but we should not over-index on a single benchmark. The right question is not "how do we replicate Greptile's 82%?" but "what is the minimum context depth that produces reviews developers actually trust?" Our tiered approach lets us measure this empirically rather than assuming the answer.

### 2. "LlamaIndex is the obvious retrieval framework choice"

The DEM-114 evaluation recommends LlamaIndex and the reasoning is sound — deepest retrieval primitives, natural extension points for code-specific components, largest integration ecosystem. But we should be honest about the risks:

- **Abstraction tax.** LlamaIndex's deep abstraction layers add latency and debugging complexity. For a code review tool where every review is latency-sensitive (developers want results in <60s), the overhead matters. The DEM-114 evaluation acknowledges this but may underweight it.
- **API churn history.** LlamaIndex has broken backward compatibility between minor versions multiple times. Building four custom components (NodeParser, three retrievers) on a churning API multiplies maintenance cost.
- **LlamaCloud commercial pressure.** VC-backed OSS follows a pattern: new capabilities land in the commercial product first. We need an exit strategy if critical retrieval primitives become LlamaCloud-only.

**Our position:** Use LlamaIndex, but with deliberate insulation. Wrap all LlamaIndex interfaces behind our own thin abstractions (`KenjutsuRetriever`, `KenjutsuNodeParser`). If LlamaIndex becomes untenable, Haystack is the migration target — similar concepts, different API, Apache-2.0 licensed. The wrapper cost is low; the optionality is high.

### 3. "Paperclip multi-agent review is our primary differentiator"

Multi-agent review is genuinely unique — no competitor has an agent orchestration platform. But "unique" and "useful" are different things. The risk: multi-agent orchestration adds latency (agent routing, parallel execution, deduplication), complexity (agent disagreement resolution, finding consolidation), and cost (multiple LLM calls per review). If a single well-prompted reviewer produces 90% of the value at 30% of the cost, multi-agent is over-engineering.

**Our position:** Ship MVP with a single general-purpose reviewer. Measure quality. Add specialized agents only when we have evidence that specialization improves precision for specific finding categories (security, performance). The orchestration plumbing exists from day one (Review Router interface), but we don't populate it until the evidence justifies it.

### 4. "False positive rate under 5% is achievable with self-reflection"

The research assumes a two-pass approach (generate + self-reflect) will get us to <5% FP. This is optimistic. Self-reflection helps, but the FP rate is fundamentally a function of context quality, prompt engineering, and the underlying model's code understanding. No competitor has publicly demonstrated <5% FP across diverse codebases. Graphite Diamond claims <3% "unhelpful" but detects only 6% of bugs — low noise because it says almost nothing.

**Our position:** Target <10% FP for MVP (still better than most competitors). Invest in prompt engineering iteration and feedback loops for continuous improvement. Treat <5% as an aspirational target that requires real-world data, not a design requirement we can architect our way to.

### 5. "Embed natural language descriptions of code, not raw code"

Greptile's data shows 12% cosine similarity improvement for NL descriptions vs raw code (0.8152 vs 0.7280). This is real but comes with tradeoffs:
- LLM call per function during indexing (~$50-100 for a large codebase)
- Description quality depends on the summarizing model — bad descriptions poison retrieval
- Descriptions can become stale faster than code (semantic drift)

**Our position:** Use NL descriptions, but with a fallback. Index both raw code embeddings and NL descriptions. If the NL description is low-confidence or stale (content hash changed but description not yet regenerated), fall back to raw code embedding. This adds storage cost (~2x) but eliminates a single point of failure in the retrieval pipeline.

---

## 1. Core Architecture

### System Boundaries

Kenjutsu operates as three loosely coupled subsystems plus an asynchronous index:

```text
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
│  ┌─────────────────────────────────────────────────────────┐│
│  │                  Index Subsystem                        ││
│  │ • AST parsing (tree-sitter)                             ││
│  │ • Embedding (Voyage-code-3 via LlamaIndex)              ││
│  │ • Incremental sync (content-hash caching)               ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

**Ingestion** receives events, processes diffs, and interfaces with git platforms. This is plumbing — it should be reliable, fast, and boring.

**Analysis** retrieves context via LlamaIndex-orchestrated retrieval pipeline, generates review findings, and scores confidence. This is where intelligence lives — it should be deep, precise, and continuously improving.

**Orchestration** routes review tasks to specialized agents, enforces governance rules, and publishes results. This is the Paperclip-native layer — it should be composable, auditable, and unique.

**Index** runs asynchronously, building and maintaining the codebase knowledge graph via tree-sitter AST parsing and LlamaIndex indexing. This is the context foundation — it should be incremental, cost-efficient, and resilient to staleness.

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

A GitHub App is the standard for production code review tools. The rate limits (5,000-12,500 req/hr vs 1,000 for Actions), exclusive Checks API access, bot identity, and marketplace distribution are all decisive advantages. Every serious competitor uses this model.

**Components:**
- FastAPI webhook server with HMAC-SHA256 verification
- GitHub App authentication (JWT → installation token, 1-hour refresh cycle)
- Event routing for `pull_request` (opened, synchronize, reopened) and `issue_comment` events
- Async task dispatch via Redis queue (or in-process queue for MVP)
- PR metadata fetching, diff retrieval, file content access
- **Debounce on `synchronize` events** — wait 30-60 seconds before starting review in case more commits follow

**Secondary:** GitHub Action for zero-infrastructure onboarding. Same analysis logic, different trigger mechanism. This is a distribution play — lower barrier to entry for individual developers and small teams who want to try before committing to an App install.

**Design decision:** Build the GitHub provider as a `GitPlatformProvider` interface from day one, but only implement GitHub initially. GitLab and Bitbucket are post-MVP. The abstraction costs almost nothing upfront and prevents a rewrite later.

### 2.2 Diff Processing Pipeline

**Approach: Proven (conservative) — study PR-Agent's patterns, implement clean**

Diff processing is algorithmic work with well-understood solutions. PR-Agent has iterated on this for years. We study their approach (hunk extension, token-aware chunking, decoupled format) and reimplement cleanly. This is legally safe — algorithms and strategies are not copyrightable.

**Pipeline:**
1. Parse unified diff into structured `PatchFile` objects
2. Convert to decoupled hunk format (separate new/old views with line numbers) — this format helps LLMs reason about change positioning for inline suggestions
3. Extend hunks to enclosing function/class boundaries via tree-sitter (dynamic context expansion)
4. Apply token-aware chunking: greedy fill within budget, language-prioritized ordering
5. Large diff handling: multi-patch mode (split into chunks, parallel LLM calls) for PRs exceeding token budget
6. Deletion omission: strip deletion-only hunks, list deleted files by name

**Token budget management:** Count tokens before every LLM call using tiktoken. Set limits based on actual model capabilities (200K for Claude Sonnet 4.5) — not PR-Agent's artificial 32K default that wastes 85% of available context. Reserve 10% output buffer. Graceful degradation — reduce context depth rather than fail.

### 2.3 Context Retrieval: LlamaIndex-Orchestrated Tiered Pipeline

**Approach: Pragmatic innovation — LlamaIndex framework with deliberate insulation**

This is the component where we deviate most from PR-Agent (diff-only) while avoiding Greptile's expensive full-repo-always approach. The tiered architecture lets us ship with meaningful context at low cost, then deepen incrementally — and measure the impact of each tier.

**Framework choice: LlamaIndex** (per DEM-114 evaluation). LlamaIndex treats retrieval as the core design problem, which matches our core problem. Its `NodeParser` and `BaseRetriever` interfaces are natural extension points for code-specific components. Four custom components, seven built-in capabilities — good leverage.

**Critical insulation layer:** All LlamaIndex interfaces are wrapped behind our own abstractions (`KenjutsuRetriever` wraps `BaseRetriever`, `KenjutsuNodeParser` wraps `NodeParser`). This protects us from LlamaIndex API churn and preserves the option to migrate to Haystack if commercial pressure or stability concerns warrant it. Pin to a specific LlamaIndex major version; upgrade deliberately, not continuously.

#### Tier 1 — Always On (Free, MVP)

These signals are computationally cheap and provide substantial context improvement over diff-only:

| Signal | Method | LlamaIndex Integration | Cost |
|---|---|---|---|
| Enclosing scope | tree-sitter AST: expand hunks to function/class boundaries | Custom `KenjutsuNodeParser` | Free |
| Import graph | tree-sitter: extract imports, resolve to files in repo | Custom `ImportGraphRetriever` | Free |
| Co-change files | `git log --follow` mining: files that historically change together | Custom `CoChangeRetriever` | Free |
| Test file matching | Path heuristics: `foo.py` ↔ `test_foo.py`, `foo.spec.ts` | Custom `TestFileRetriever` | Free |
| Type definitions | tree-sitter: resolve type annotations to their definitions | Included in `ImportGraphRetriever` | Free |

**Honest assessment:** Tier 1 gets us meaningfully past diff-only but won't match the depth of Greptile or CodeRabbit. That's acceptable for MVP. The question is whether the gap matters enough to delay shipping.

#### Tier 2 — On-Demand (Medium Cost, Post-MVP Phase 1)

Activated for PRs that touch shared code, APIs, or cross-cutting concerns. LlamaIndex provides these as configuration, not custom code:

| Signal | Method | LlamaIndex Component | Cost |
|---|---|---|---|
| Semantic search | Function-level embeddings (Voyage-code-3, 1024 dims) | `VectorIndexRetriever` | Medium |
| Hybrid retrieval | BM25 keyword + vector similarity, weighted fusion | `QueryFusionRetriever` | Medium |
| Cross-encoder reranking | Top-50 candidates → top-10 via reranker | `CohereRerank` / `SentenceTransformerRerank` | Medium |
| Query routing | Route simple PRs through Tier 1, complex through full retrieval | `RouterQueryEngine` | Free |

**Embedding strategy:** Embed both natural language descriptions and raw code for each function (dual index). NL descriptions for primary retrieval (12% quality improvement per Greptile data), raw code as fallback when descriptions are stale or low-confidence. This doubles storage cost but eliminates a single point of failure.

**Chunking:** Function-level via tree-sitter AST. Include class header + imports with each chunk for context. No mid-function splitting. Backed by Greptile's empirical data (7% similarity drop from noise) and academic evidence (cAST, EMNLP 2025: higher precision correlates with better generation more than recall).

**Incremental indexing:** Content-hash each chunk. On file change, re-chunk, compare hashes, only re-embed changed chunks. Re-index on PR creation against base branch; full re-index on default branch merge.

#### Tier 3 — Deep Analysis (Higher Cost, Post-MVP Phase 2)

For complex PRs, architectural changes, or security-sensitive reviews:

| Signal | Method | Cost |
|---|---|---|
| Agentic multi-hop search | LLM-guided dependency tracing through code graph (consider LangGraph) | High |
| Historical review matching | Embed past review decisions, retrieve similar patterns | Medium |
| Issue tracker context | Linked Jira/Linear/GitHub Issues for business context | Low |

**Honest assessment:** Tier 3 is where we would approach Greptile's depth. But it's also where costs multiply. We should build Tier 3 only after measuring Tier 2's impact on review quality. If Tier 1+2 gets us to 70-80% of the quality of full agentic search at 20% of the cost, Tier 3 may not be worth the investment for most users.

### 2.4 Review Engine

**Approach: Proven foundation + pragmatic innovation in filtering**

#### LLM Integration

**Primary model: Claude Sonnet 4.5** — best cost/quality ratio for code review. 200K context window. Strong structured output. $0.22-0.35 per typical PR.

**Fallback: GPT-4o** — different model family reduces correlated failures. Cross-provider fallback is important because single-provider outages have historically lasted hours.

**Deep analysis: Claude Opus 4.6** — reserved for self-reflection scoring and Tier 3 complex analysis on high-risk PRs only. $1.10-1.75 per PR. Used when the stakes justify the cost, not routinely.

**Integration via LiteLLM** — unified interface to 100+ providers. Model-specific handling (temperature, system messages, reasoning effort) managed through a thin adapter layer. This is a solved problem; LiteLLM is the standard.

#### Prompt Architecture

Jinja2 templates with Pydantic schema-driven structured output. This pattern (embedding output schemas in prompts, parsing structured YAML/JSON responses) is PR-Agent's most valuable contribution. We reimplement the pattern, not the code.

**Template structure:**
```text
System: Role definition + output schema (Pydantic model)
Context: Codebase summary + retrieved context chunks (cached via prompt caching)
Diff: Formatted hunks with line numbers
Instructions: Review criteria + severity definitions
```

**Prompt caching:** Claude and OpenAI support prompt caching — up to 90% cost reduction for repeated system prompts + codebase summaries. The system prompt + cached context (60% of token budget) becomes near-free after the first review in a session. This is the single most important cost optimization.

#### False Positive Management

**Realistic target: <10% FP rate for MVP.** This is already better than most competitors. <5% is an aspirational target that requires real-world feedback loop data, not just architecture.

**Two-pass review:**
1. **Generation pass:** Primary LLM generates findings with severity and confidence scores
2. **Self-reflection pass:** Second LLM call (same or cheaper model) scores each finding on relevance, accuracy, and actionability. Findings below threshold are suppressed.

**Severity-first output:** Every finding is ranked: `critical` → `warning` → `info`. The review output leads with critical findings. Style nitpicks are suppressed by default (opt-in via configuration). This addresses the universal complaint that AI reviewers bury real bugs under style noise.

**Post-MVP: Feedback loop.** Track which findings developers accept vs dismiss per repository. Use acceptance rates to tune confidence thresholds. This is where the real FP improvement comes from — not from architecture, but from empirical calibration.

### 2.5 Orchestration: Paperclip-Native Review Routing

**Approach: Strategic investment — build the plumbing now, populate it when evidence supports it**

The Orchestration layer is where Kenjutsu becomes something competitors cannot replicate. But we are deliberate about when we activate multi-agent capabilities.

#### MVP: Single Reviewer + Governance Metadata

The Review Router exists but routes everything to a single general-purpose reviewer. The value of the Orchestration layer in MVP is not multi-agent — it's **governance metadata**:

Every review finding carries:
- Which agent produced it (even if there's only one)
- What context was available (Tier 1/2/3)
- What model was used
- Confidence score
- Timestamp and review request ID

This metadata enables compliance audit trails from day one. When EU AI Act (August 2026) and Colorado AI Act (June 2026) deadlines arrive, we have the data structure already in place. Adding this metadata to findings is cheap; retrofitting it later is expensive.

#### Post-MVP: Specialized Agents (Evidence-Gated)

Add specialized agents only when we have evidence from MVP usage that specialization improves precision for specific finding categories:

```text
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

**Criteria for adding a specialized agent:** The general reviewer must demonstrate a measurable quality gap in a specific domain (e.g., missing security findings that a security-focused prompt would catch) across a significant sample of real reviews. We don't add agents because they sound good — we add them because the data says the general reviewer is leaving value on the table.

### 2.6 Publisher

**Approach: Proven (conservative)**

**Pending review pattern:** Create review → accumulate all comments → submit atomically. One notification to the PR author, not N. This is what CodeRabbit and PR-Agent do — it's the correct UX.

**Dual output:**
- **PR Review:** Inline comments on specific lines, suggestion blocks for one-click fixes, overall review summary
- **Check Run:** Summary status with annotations. GitHub Apps exclusive — gives us status check integration for branch protection.

**Rate limit awareness:** Content creation limit (80 req/min, 500 req/hr) is the binding constraint. Batch aggressively. For large PRs, prioritize findings by severity rather than exhaustively commenting.

---

## 3. Data Flow

### Happy Path: PR Review

```text
1. GitHub sends pull_request webhook (opened/synchronize)
   └→ Webhook server verifies HMAC-SHA256 signature
   └→ Debounce (30-60s for synchronize events)
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
   └→ Tier 1 context retrieval via LlamaIndex custom retrievers
   └→ [If indexed] Tier 2 retrieval via LlamaIndex built-in hybrid search
   └→ Renders prompt with diff + context + instructions
   └→ LLM call → structured findings
   └→ Self-reflection pass → filtered, scored findings

5. Orchestration collects findings from all reviewers
   └→ Deduplicates across reviewers
   └→ Applies governance rules (severity thresholds, team config)
   └→ Attaches provenance metadata to each finding
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

**Rationale:** Best LLM ecosystem (LiteLLM, tiktoken, Anthropic SDK), mature tree-sitter bindings (py-tree-sitter), FastAPI for async webhooks, PyGithub for GitHub API, LlamaIndex is Python-native. PR-Agent's architecture (studied, not forked) is Python — learnings transfer directly.

**Alternative considered: TypeScript.** Closer to GitHub/VS Code ecosystem. Better for future IDE extensions. Mastra (DEM-114 evaluation) has strong RAG capabilities and is TypeScript-only, which means we lose access to it by choosing Python. However, LlamaIndex's retrieval depth is more important than Mastra's RAG+agent combination, and LlamaIndex is Python. Revisit TypeScript for IDE components post-MVP.

### Key Dependencies

| Library | Purpose | Why |
|---|---|---|
| FastAPI | Webhook server | Async, high-performance, well-documented |
| LiteLLM | Multi-LLM provider | 100+ providers, unified interface, avoids lock-in |
| LlamaIndex | Retrieval orchestration | Deepest retrieval primitives, code-specific extension points, 300+ integrations |
| py-tree-sitter | AST parsing | Universal parser, production-proven (Neovim, Zed, Helix) |
| tiktoken | Token counting | Fast, accurate, model-aware |
| Voyage-code-3 | Code embeddings | SOTA for code retrieval, Matryoshka dimensions (via LlamaIndex integration) |
| LanceDB | Vector storage (MVP) | Embedded, zero-infra, good Python support (via LlamaIndex integration) |
| PyGithub | GitHub API | Mature, well-maintained |
| Jinja2 | Prompt templates | Flexible conditional rendering |
| Pydantic | Structured output + config | Type validation, JSON schema generation, settings management |
| Redis (or dramatiq) | Task queue | Async processing, debouncing |

### What We Explicitly Avoid

- **Dynaconf** — PR-Agent's global state pattern (200+ `get_settings()` calls) is their worst architectural decision. Use Pydantic Settings with explicit injection.
- **Monolithic dependencies** — Use optional extras: `pip install kenjutsu[github]`, `kenjutsu[embeddings]`. Don't force boto3 on users who only need GitHub.
- **Hardcoded command registry** — Design a plugin system from day one. Even if MVP has one review command, the extension point exists.
- **Graph-RAG systems** (LightRAG, GraphRAG, R2R, Cognee) — Per DEM-114 evaluation, these use LLM entity extraction designed for prose documents, not code. Code graphs should be derived from AST parsing (tree-sitter), not LLM extraction. The cost difference is orders of magnitude and AST parsing is deterministically correct.

---

## 5. Configuration

### User-Facing Configuration

`.kenjutsu.toml` in repository root. Zero-config operation with sensible defaults. Override only what you need.

```toml
[kenjutsu]
auto_review = true              # Review on PR open/push
review_on_draft = false         # Skip draft PRs
severity_threshold = "warning"  # Minimum severity to comment (critical/warning/info)

[kenjutsu.context]
tier = "auto"                   # auto | tier1 | tier2 | tier3
# auto: Tier 1 always, Tier 2 for shared code, Tier 3 for high-risk changes

[kenjutsu.ignore]
paths = ["*.lock", "*.generated.*", "vendor/", "node_modules/"]

[kenjutsu.model]
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
| LlamaIndex for retrieval | 7 built-in capabilities, 4 custom components | API churn, abstraction overhead, LlamaCloud pressure | Insulation layer (`KenjutsuRetriever`), Haystack as migration target |
| Tiered context (not full index from day one) | Faster MVP, lower initial cost, measurable per-tier impact | Tier 1 quality gap vs full-index competitors | Ship fast, measure, invest in tiers that demonstrably improve quality |
| Multi-agent via Paperclip (evidence-gated) | Unique differentiation, governance capability | Complexity if activated prematurely | Single reviewer MVP; add agents only when data supports it |
| Dual embedding (NL + raw code) | 12% retrieval improvement with fallback safety | 2x storage cost for embeddings | Storage is cheap; retrieval quality is expensive to fix |
| Python (not TypeScript) | Best LLM + retrieval ecosystem, LlamaIndex native | Weaker for IDE extensions; loses access to Mastra | IDE components can be TypeScript; core analysis stays Python |
| Precision over recall (<10% FP target) | Developer trust, lower noise | May miss some real issues | Self-reflection pass, severity ranking, feedback loop for continuous improvement |
| GitHub-first (not multi-platform) | Focused effort, faster shipping | Excludes GitLab/Bitbucket users initially | Provider abstraction exists from day one; add platforms post-MVP |

### Decisions We Defer (and Why)

| Decision | Deferral Rationale | When to Decide |
|---|---|---|
| Multi-repo intelligence | Requires significant index infrastructure; single-repo is sufficient for MVP | After Tier 2 context is proven (Phase 3+) |
| Pre-commit / IDE integration | Different integration surface; PR review is the established user expectation | After core review quality is validated |
| Feedback loop learning | Needs volume of review data to be useful; premature optimization of FP filtering | After 1000+ reviews across real repositories |
| Specialized review agents | Need evidence of quality gaps in general reviewer by domain | After MVP review quality is measured across diverse PRs |
| Tier 3 agentic search | High cost, complex implementation; Tier 1+2 may cover most value | After measuring Tier 2 impact on review quality |

---

## 7. Phased Delivery

### Phase 1: Foundation (Weeks 1-4)

**Goal:** Working GitHub App that can receive PRs, process diffs, and post basic review comments.

- GitHub App registration, webhook server, signature verification
- GitHub provider (auth, diff fetching, file retrieval, review publishing)
- Diff processor (parsing, hunk formatting, token budgeting, chunking)
- Configuration system (`.kenjutsu.toml` with defaults)
- CLI for local testing

**Exit criteria:** Can receive a PR webhook, fetch diff, process it, and post a formatted diff summary as a PR comment.

### Phase 2: Review Intelligence (Weeks 5-8)

**Goal:** Meaningful review quality with Tier 1 context and false positive filtering.

- LLM integration via LiteLLM, Jinja2 prompt templates, Pydantic structured output
- Review engine (severity scoring, finding generation, Markdown formatting)
- Tier 1 context via custom LlamaIndex components (tree-sitter import graph, hunk extension, co-change analysis, test file matching)
- Self-reflection pass for false positive filtering
- Publisher (pending review pattern, Check Runs)

**Exit criteria:** Reviews real PRs with context-aware findings, severity ranking, and <10% false positive rate. Posts as a proper GitHub review with inline comments.

### Phase 3: Production Hardening (Weeks 9-12)

**Goal:** Production-ready MVP with governance metadata.

- Prompt engineering iteration on real PRs (target: improve FP rate continuously)
- Large PR handling (multi-patch mode), edge cases, error handling
- Paperclip orchestration integration (Review Router, single general reviewer)
- Governance metadata on all findings (agent, model, context tier, confidence)
- Deployment packaging (Docker), documentation
- Internal benchmark suite for quality measurement

**Exit criteria:** Installable on real repositories. Governance metadata attached to all findings. Benchmarked against PR-Agent and CodeRabbit on a standard PR set.

### Phase 4: Context Depth (Weeks 13-16, Post-MVP)

**Goal:** Tier 2 context for measurably improved review quality.

- Index subsystem: tree-sitter AST → NL descriptions + raw code embeddings → Voyage-code-3
- LlamaIndex indexing pipeline with incremental content-hash caching
- Hybrid BM25 + vector retrieval via `QueryFusionRetriever`, cross-encoder reranking
- `RouterQueryEngine` for automatic tier selection
- Prompt caching optimization
- A/B comparison: Tier 1 only vs Tier 1+2 on the same PR set

**Exit criteria:** Measurable improvement in review quality over Tier 1 baseline (bug detection rate, finding relevance, developer acceptance rate).

### Phase 5: Multi-Agent & Governance (Weeks 17-20, Post-MVP)

**Goal:** Specialized review agents (if evidence supports) and enterprise governance.

- Analyze MVP review data for quality gaps by domain (security, performance, architecture)
- If gaps exist: build specialized reviewer agents with domain-focused prompts
- Review Router with file-type and change-pattern-based routing
- Governance dashboard (finding provenance, trust scores, audit trails)
- GitHub Action distribution for zero-infra onboarding

**Exit criteria:** Evidence-based decision on specialized agents. Governance audit trail complete for compliance use cases. Two distribution channels (App + Action).

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

| PR Size | Input Tokens | Output Tokens | Cost (no caching) | Cost (with prompt caching) |
|---|---|---|---|---|
| Small (1-5 files) | ~30K | ~3K | $0.14 | $0.06 |
| Typical (5-15 files) | ~60K | ~5K | $0.26 | $0.10 |
| Large (15-50 files, multi-patch) | ~200K | ~15K | $0.83 | $0.31 |

---

## 9. Risk Assessment

### Risks We Accept

| Risk | Likelihood | Impact | Why We Accept It |
|---|---|---|---|
| Prompt engineering iteration takes longer than budgeted | High | Medium | This is empirical work, not architecture. The risk is schedule, not feasibility. Budget 3-4 weeks. |
| Tier 1 context quality gap vs Greptile | High | Medium | Tier 1 still beats diff-only. We compete on precision initially, not detection breadth. Tier 2 is planned. |
| LlamaIndex API churn impacts custom components | Medium | Medium | Insulation layer limits blast radius. Haystack is migration target. Pin versions. |

### Risks We Mitigate

| Risk | Mitigation |
|---|---|
| False positive rate above target | Two-pass review + severity ranking + feedback loop (post-MVP). Target <10% for MVP, iterate toward <5%. |
| LLM API reliability | Cross-provider fallback (Claude → GPT-4o). Retry with exponential backoff. |
| LlamaIndex commercial pressure | Insulation layer + Haystack migration target + MIT license fork option. |
| GitHub rate limits | Pending review pattern, Check Run annotations, debounce on updates. |
| IP risk from studying PR-Agent | Clean-room reimplementation. Study patterns only. No post-AGPL code. |

### Risks We Avoid

| Risk | How |
|---|---|
| AGPL contamination | Build from scratch. No fork. |
| Vendor lock-in | LiteLLM for LLMs, LlamaIndex abstraction for retrieval, provider abstraction for git platforms. |
| Premature multi-agent complexity | Evidence-gated: single reviewer first, add agents only when data supports it. |
| Over-engineering the MVP | Feature scope: `/review` only. No `/describe`, `/improve`, `/ask` until core quality is proven. |

---

## 10. What Makes This "Balanced"

This architecture earns the "balanced" label through three specific mechanisms:

**Evidence-gated investment.** We don't build capabilities because they sound good. Each tier of context depth, each specialized agent, each advanced retrieval feature requires evidence of impact before it moves from "designed" to "built." The interfaces exist from day one; the implementations follow the data.

**Layered risk.** Conservative at the foundation (proven infrastructure, clean IP, standard tools), pragmatic in the middle (LlamaIndex with insulation, tiered context with measurement), ambitious at the differentiation layer (Paperclip governance, multi-agent orchestration). Failure at any layer doesn't cascade — you can run a useful review tool with just Tiers 1 and 2, a single reviewer, and no governance metadata.

**Honest about what we don't know.** We don't know if <5% FP is achievable without a feedback loop. We don't know if Tier 2 context depth justifies its cost. We don't know if specialized agents beat a single well-prompted reviewer. The architecture doesn't pretend to know these things — it creates the structure to learn them quickly.

The result: a system that is useful from week 8 (basic review with Tier 1 context and severity ranking), measurably better by week 16 (Tier 2 context with A/B data), and enterprise-ready by week 20 (governance + compliance). Each phase delivers standalone value and generates data for the next phase's investment decisions.

---

## Sources

This architecture synthesizes findings from:
- Competitive analysis (DEM-105): Market positioning, pricing, feature gaps
- PR-Agent deep-dive (DEM-106): Architecture patterns, diff processing, prompt engineering, AGPL finding
- GitHub integration (DEM-107): App vs Action, rate limits, API patterns
- Context/RAG strategies (DEM-108): Embedding approaches, chunking, retrieval pipelines
- Differentiation (DEM-109): Market gaps, positioning options, governance opportunity
- Technical feasibility (DEM-110): Build vs fork, MVP scope, timeline, cost projections
- Retrieval framework evaluation (DEM-114): LlamaIndex recommendation, 10-framework comparison, graph-RAG category mismatch finding
