# Kenjutsu Architecture Specification — v3

**Date:** 2026-03-24
**Status:** Draft
**Author:** Board + Claude (brainstorming session)
**Previous:** v2 preserved as `kenjutsu-architecture-v2.md`
**Changes from v2:** Restructured phasing around sequential bet validation. SurrealDB deferred to Phase 3 (evidence-gated). Added go/no-go criteria between phases. Separated predictive warnings from defect findings in UX. Added DBOS abstraction boundary. Noted SurrealDB BSL 1.1 licensing risk. Scoped language claims with explicit blind spots. Added graph extraction accuracy contract, overlay semantics, tenant isolation, performance budgets.

---

## 1. Product Overview

Kenjutsu is a SaaS AI code review tool that reviews GitHub pull requests with codebase-aware context.

**Initial target:** Mid-size engineering teams (10-50 devs), private GitHub Cloud repos, TypeScript/JavaScript and Python codebases. Developer-led adoption via free tier, expanding to enterprise as governance features mature.

**Core value proposition:** High-signal, governance-ready code review. Precision over recall — only speak when it matters.

**What makes it different:**
- **Branch-consistent structural context** — the reviewer sees new symbols, renamed functions, and changed edges in the PR, not a stale snapshot of the default branch
- **Deterministic-first evidence pipeline** — AST-grep and structural analysis run before the LLM, producing the highest-quality findings at zero LLM cost
- **Predictive analysis** — "what did you forget to change?" via structural analysis, zero LLM cost
- **Evidence-based signal taxonomy** — findings carry independent dimensions of origin, confidence, severity, and publishability
- **Governance and audit** — every review decision traceable to a specific model, context version, and evidence chain

**What it is NOT:**
- Not a Paperclip plugin or Paperclip-dependent
- Not a fork of PR-Agent (AGPL blocks commercial use)
- Not a linter (the LLM is one signal source among several)

**First-class languages at launch:** TypeScript/JavaScript and Python. Go, Java, and Rust get basic tree-sitter AST parsing but no deterministic rules or import resolution until the wedge is validated.

**Known blind spots:** Dynamic dispatch (Python monkey-patching, JS dynamic imports, reflection, runtime-generated code) produces incomplete call/import graphs. The system is honest about this — findings from structural analysis carry a `graph_completeness` flag per language.

---

## 2. The Three Bets

This architecture rests on three layered bets. They are ordered by confidence and must be validated sequentially — each phase proves or disproves the next bet before committing further investment.

### Bet A: Structural, branch-consistent code context improves PR review quality.
**Confidence:** High. Evidence: Greptile's 82% vs 44% benchmark (caveats acknowledged), universal developer complaint about "context blindness," and the simple logic that seeing what calls a changed function is better than not seeing it.
**Validated by:** Phase 1-2. Bare mirrors, tree-sitter, git log, one LLM, evaluation harness.
**Go/no-go:** Measured by accepted-finding rate lift over diff-only baseline.

### Bet B: A persistent semantic graph is required to get that benefit at scale.
**Confidence:** Medium. In-memory tree-sitter analysis works for small/medium repos. At scale (>100K functions, cross-repo), a persistent graph with incremental indexing, co-change history, and version control becomes necessary.
**Validated by:** Phase 3. SurrealDB integration, only after Bet A is proven.
**Go/no-go:** Layer 1 quality plateau — if tree-sitter + git log alone isn't sufficient, the graph earns its place.

### Bet C: Semantic retrieval (embeddings + reranking) and agentic search add further value.
**Confidence:** Lower. Embeddings help for "find similar code" queries but may not materially improve review quality beyond structural context. Agentic search is expensive and nondeterministic.
**Validated by:** Phase 4. Only after Bet B is proven.
**Go/no-go:** Accepted-finding rate plateau — if structural + graph retrieval isn't sufficient, semantic search earns its place.

### Go/No-Go Criteria (90-Day Proof)

| Signal | Prove (proceed to next bet) | Disprove (simplify) |
|--------|---------------------------|-------------------|
| Accepted-finding rate | >15% lift on refactor/API/security PRs vs diff-only | Flat vs diff-only |
| Graph-assisted finding share | >20% of accepted findings originate from structural/graph sources | Graph findings rarely accepted |
| FP rate | Stays below target per confidence tier | Rises despite tuning |
| Latency impact | P95 increase < 20 seconds | Latency/cost grows faster than quality |
| Predictive warning utility | Users act on >30% of predictive warnings | Users dismiss/disable at high rates |
| Index freshness | Freshness failures < 5% of reviews | Frequent stale-context incidents erode trust |

---

## 3. System Architecture

### 3.1 High-Level Overview

The architecture evolves across phases. Phase 1-2 is deliberately simple. Complexity is added only when metrics justify it.

**Phase 1-2 Architecture (Prove Bet A):**

```text
                          +---------------+
                          |    GitHub      |
                          |   Webhooks     |
                          +-------+-------+
                                  |
                                  v
+------------------------------------------------------------------+
|                       Kenjutsu Service                            |
|                                                                    |
|  +----------+    +------------+    +-------------------------+     |
|  | Webhook  |--->| Orchestrator|--->|   Pipeline Workers      |     |
|  | Server   |    | (PgSQL)    |    |                         |     |
|  | (FastAPI)|    |            |    |  1. Sha Guard            |     |
|  +----------+    +------------+    |  2. Diff Processor       |     |
|                                     |  3. Structural Context   |     |
|                                     |  4. Deterministic Analysis|    |
|                                     |  5. LLM Review           |     |
|                                     |  6. Evidence Scorer      |     |
|                                     |  7. Publisher             |     |
|                                     +------------+-------------+     |
|                                                  |                   |
|  +--------------------------+  +-----------------+-----------------+ |
|  |      PostgreSQL          |  |   Repo Mirrors (bare clones)      | |
|  |                          |  |   Persistent, git fetch on webhook | |
|  |  tenants | audit_log     |  |   tree-sitter parsing source      | |
|  |  reviews | findings      |  |   git log mining source            | |
|  |  configs | workflow state|  |                                    | |
|  |  webhook_events          |  +------------------------------------+ |
|  +--------------------------+                                        |
|                                                                      |
|  +--------------------------+                                        |
|  |  LLM Layer (LiteLLM)    |                                        |
|  |  Claude | GPT-5.4 |      |                                        |
|  |  Gemini | GLM      |     |                                        |
|  +--------------------------+                                        |
+----------------------------------------------------------------------+
```

**Phase 3+ Architecture (If Bet A proven, add graph):**

SurrealDB added as Code Semantic Graph. PostgreSQL remains for business data. Diagram adds SurrealDB box with graph nodes, edges, embeddings, BM25.

**Phase 4+ Architecture (If Bet B proven, add semantic retrieval):**

Embedding pipeline, reranking, and Layer 3 agentic search added to the existing graph.

### 3.2 Data Store Boundaries (Phase 1-2)

| Store | Owns | Why |
|-------|------|-----|
| **PostgreSQL** | Tenants, configs, reviews, findings, audit log, workflow state, webhook events | Transactional business data. Proven at scale. |
| **Repo Mirrors** | Persistent bare clones of each repo | Reliable tree-sitter parsing, git log mining, rename detection, no API rate consumption |

### 3.3 Data Store Boundaries (Phase 3+, if justified)

| Store | Owns | Why |
|-------|------|-----|
| **PostgreSQL** | Same as above | Same as above |
| **SurrealDB** | Code Semantic Graph: versioned code chunks, structural edges, temporal edges, embeddings, BM25 | Graph-native queries, vector + full-text in one engine |
| **Repo Mirrors** | Same as above | Same as above |

### 3.4 Key Technology Choices

| Layer | Choice | Why |
|-------|--------|-----|
| **Language** | Python 3.12+ | Best LLM ecosystem, tree-sitter bindings, FastAPI, LiteLLM |
| **Web framework** | FastAPI | Async, high-performance, OpenAPI docs |
| **Workflow orchestration** | DBOS (behind internal interface) | PostgreSQL-backed durability, built-in rate limiting |
| **Business database** | PostgreSQL | Proven, transactional |
| **Code intelligence (Phase 3+)** | SurrealDB (BSL 1.1 license — see risk assessment) | Graph + vector + BM25 in one engine |
| **AST parsing** | py-tree-sitter | Universal parser, 100+ languages |
| **LLM abstraction** | LiteLLM | Unified interface across all frontier providers |
| **Token counting** | LiteLLM token_counter | Model-aware counting across all providers |
| **Embeddings (Phase 4+)** | Voyage-code-3 (primary), Nomic Embed Code (fallback) | Best code retrieval, open-source fallback |
| **Reranking (Phase 4+)** | Jina Reranker v2, Voyage Rerank 2.5 | Only code-benchmarked reranker |
| **GitHub API** | PyGithub or httpx | PR fetching, review publishing |
| **Prompt templates** | Jinja2 | Conditional rendering, per-language variations |
| **Structured output** | Pydantic | Type validation, JSON schema for LLM output |
| **Test infrastructure** | Testcontainers | Tests declare their own infrastructure as code — same behavior local and CI |

### 3.5 Testing Strategy

Tests bring their own infrastructure via Testcontainers. No manual database setup, no "works on my machine," no divergence between local and CI.

**Test layers:**

| Layer | Directory | Infrastructure | Speed |
|-------|-----------|---------------|-------|
| Unit tests | `tests/unit/` | None — pure logic, no I/O | < 1 second |
| Integration tests | `tests/integration/` | Testcontainers (PostgreSQL, SurrealDB Phase 3+) | 10-30 seconds |
| End-to-end tests | `tests/e2e/` (future) | Testcontainers + GitHub API mock | 30-60 seconds |

**Fixture pattern:**

```python
# tests/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres_url():
    """Spin up a fresh PostgreSQL for the test session."""
    with PostgresContainer("postgres:16") as pg:
        yield pg.get_connection_url()

# Phase 3 addition — just add another fixture
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

@pytest.fixture(scope="session")
def surrealdb_url():
    """Spin up SurrealDB for graph integration tests."""
    with DockerContainer("surrealdb/surrealdb:v2") \
        .with_exposed_ports(8000) \
        .with_command("start --user root --pass root") as surreal:
        wait_for_logs(surreal, "Started web server")
        host = surreal.get_container_host_ip()
        port = surreal.get_exposed_port(8000)
        yield f"ws://{host}:{port}"
```

**CI implications:** GitHub Actions `ubuntu-latest` has Docker available, so Testcontainers works natively. The CI `services:` block for PostgreSQL is replaced by Testcontainers — tests own their infrastructure, CI just runs pytest. For non-containerized services (GitHub API, LLM providers), CI integration tests use contract fixtures or recorded HTTP mocks — never live API calls. Live smoke tests run in staging only (see Issue 1.11).

**Why this matters for Kenjutsu:** As the architecture evolves (PostgreSQL Phase 1 → add SurrealDB Phase 3 → add mock APIs Phase 4), the test infrastructure grows by adding fixtures, not rewriting CI workflows.

### 3.6 DBOS Abstraction Boundary

Business logic is plain async functions. The orchestration layer adds durability. This protects against DBOS lock-in.

```python
# Business logic — no DBOS dependency
async def process_diff(pr_metadata: PrMetadata) -> ReviewRequest:
    mirror = get_mirror(pr_metadata.repo_id)
    diff = mirror.diff(pr_metadata.base_sha, pr_metadata.head_sha)
    patches = parse_diff(diff)
    extended = extend_hunks_with_ast(patches, mirror)
    return build_review_request(extended, pr_metadata)

# Orchestration layer — thin wrapper, swappable
@DBOS.step()
async def step_process_diff(pr_metadata: PrMetadata) -> ReviewRequest:
    return await process_diff(pr_metadata)

# Workflow composition — also swappable
@DBOS.workflow()
async def review_pr(pr_metadata: PrMetadata):
    if not await step_sha_guard(pr_metadata):
        return {"status": "aborted", "reason": "stale_sha"}
    diff = await step_process_diff(pr_metadata)
    # ... remaining steps
```

If DBOS is replaced, only the `step_*` wrappers and workflow composition change. Business functions are untouched.

---

## 4. Trust Mechanics

Trust mechanics are the foundation. Before retrieval sophistication, the system must be correct, predictable, and safe.

### 4.1 Review Identity

Every review uniquely identified by `(repo_id, pr_number, head_sha)`. This is the **supersession key** — at most one canonical review per key. Reruns replace, not duplicate.

### 4.2 Sha Guard

- **Before processing:** Verify `head_sha` is current via GitHub API
- **Before publishing:** Re-check `head_sha`. If stale, cancel — do not publish.
- **Mid-review commit:** Cancel in-flight workflow, debounce, re-enqueue for new sha.

**Hard rule:** Never publish findings against an outdated `head_sha`.

### 4.3 Finding Fingerprints

`sha256(file_path + finding_category + normalized_description_hash + code_context_hash)`

Enables: dedup across reruns, suppression tracking, "still present" detection, FP rate measurement.

Line numbers are NOT part of the fingerprint — code can shift lines without changing the finding.

**Stability requirement:** Fingerprints must be robust to minor wording changes in LLM output. The `normalized_description_hash` uses a canonicalized form (lowercase, stripped whitespace, key-phrase extraction) rather than raw LLM text.

### 4.4 Stale Review Handling

| Event | Behavior |
|-------|----------|
| New commit while review in progress | Cancel in-flight, debounce, re-enqueue new sha |
| New commit after review published | Mark previous as `superseded`. New review on publish. |
| Force push | Treat as new sha. Previous auto-superseded. |
| PR closed then reopened | New review on current sha if auto-review enabled |

### 4.5 Idempotent Publishing

- Check for existing review for this `(pr_number, head_sha)` before creating
- Store `github_review_id` and `github_comment_ids` — retries update, not create
- Check Run idempotent via `external_id` = `review_id`

### 4.6 Prompt Injection Defense

- Input isolation: untrusted content in delimited sections (`<user_code>...</user_code>`)
- Output validation: Pydantic schemas, freeform text cannot escape into system actions
- No code execution: tree-sitter parses, never executes
- Finding sanitization: scan for injected markdown/links before publishing

### 4.7 Sensitive Finding Handling

- Do NOT post sensitive values (secrets, credentials, PII) in PR comments
- Post redacted finding: "Potential hardcoded credential at line N. See audit log."
- Full details in audit log only
- Auto-elevated to `severity: critical`

**Detection:** Regex patterns + entropy analysis for initial launch. Integration with external scanners (future).

### 4.8 Degraded-Mode Policy

| Condition | Free Tier | Pro/Enterprise Tier |
|-----------|-----------|-------------------|
| SurrealDB unavailable (Phase 3+) | Continue with tree-sitter-only context | Continue with tree-sitter-only context (graph is additive, not required) |
| All LLM providers down | Check Run: "Review delayed" | Same + SLA-tracked incident |
| Publishing fails | DBOS retries, no LLM re-computation | Same |
| Repo not yet indexed (Phase 3+) | tree-sitter-only context | Same |

**Key change from v2:** Because Phase 1-2 doesn't depend on SurrealDB, there is no "degraded mode" — tree-sitter from bare mirrors IS the primary path. SurrealDB degradation only matters in Phase 3+, and the fallback is the same system that proved itself in Phase 1-2.

---

## 5. Pipeline Flow

### 5.1 PR Review Pipeline (Phase 1-2)

**Step 1 — Webhook Reception** (< 500ms)
- Validate HMAC-SHA256 signature
- Persist raw webhook to `webhook_events` (durable, replayable, idempotent by `delivery_id`)
- Debounce: on `synchronize`, timer resets on each new event, enqueue after 30-60s of quiet
- Enqueue workflow with `(repo_id, pr_number, head_sha)` as idempotency key
- Return 200 immediately

**Step 2 — Sha Guard** (< 1s)
- Fetch current PR from GitHub API
- If `head_sha` doesn't match: abort
- Record `base_sha`, `head_sha` on review record

**Step 3 — Diff Processing** (2-5s)
- Diff from bare mirror (`git diff base_sha..head_sha`)
- Parse into structured patches
- tree-sitter AST: extend hunks to enclosing function/class
- Token budget management, multi-pass for large PRs
- Deletion summarization: deletion-only hunks are summarized (not omitted) — removed checks, guards, or validation code can be exactly where the bug is

**Step 4 — Structural Context** (1-5s)
- All from bare mirror + tree-sitter, no external database:
  - Parse changed files: extract functions, classes, imports, call sites, type annotations
  - Parse files imported by changed files: extract their signatures/contracts
  - Reverse imports: scan repo for files that import the changed files (callers/consumers)
  - Co-change analysis: `git log` mining for files that historically change together
  - Test file matching: path heuristics (`foo.py` → `test_foo.py`)
  - Enclosing scope expansion
- **Branch-consistent:** tree-sitter parses from `head_sha` in the bare mirror, so new/renamed/changed symbols in the PR are visible
- Output: structural context package

**Step 5 — Deterministic Analysis** (1-3s)
- AST-grep pattern matching for 5 first-class languages
  - `origin: deterministic`, `confidence: verified`
  - Scoped to: hardcoded credentials, SQL injection patterns, unreachable code, common bug patterns per language
- Structural checks from Step 4 data:
  - Removed function parameters still passed by callers
  - Changed return types
  - Removed exports still imported elsewhere
  - `origin: structural`, `confidence: high`
  - **Scope limitation:** These checks use tree-sitter AST analysis, NOT a type checker. They catch syntactic structural breakage for the 5 first-class languages. Deep type inference, generics resolution, and runtime behavior are out of scope.
- Predictive warnings:
  - Co-change: "File B usually changes with A (85% probability) — was this intentional?"
  - Missing tests: new/changed functions with no matching test file
  - `origin: predictive`, `confidence: high`
- Deterministic findings fed into LLM prompt: "these are already found — focus elsewhere"

**Step 6 — LLM Review** (10-60s)
- Model selection by complexity score:
  - `complexity = file_count * 2 + line_count / 100 + file_type_weight + caller_count / 10`
  - file_type_weight: +5 for `**/migration*`, `**/auth/**`, `**/schema*`, `**/api/**`
  - < 20 = Sonnet, > 50 = Opus, else Sonnet
- Jinja2 prompt: system + diff + structural context + deterministic findings + output schema
- LLM call via LiteLLM, structured output parsing with repair
- Multi-pass for large PRs: chunk, review each, deduplicate, synthesize

**Step 7 — Evidence Scoring** (5-15s)
- For each LLM finding, check if structural data from Step 4 supports it:
  - Structural evidence confirms → `confidence: high`
  - No structural confirmation → cross-model self-reflection (batched, different model family)
  - Self-reflection >= 7 → `confidence: medium`
  - Self-reflection < 7 → `confidence: low` (suppressed)
- Self-reflection fallback: primary scorer → secondary scorer → same-model
- Meta-synthesis: merge deterministic + LLM findings, deduplicate by fingerprint, apply publishability rules

**Step 8 — Sha Re-check & Publish** (2-5s)
- Re-check `head_sha`. If stale: abort.
- Create pending GitHub review
- **Defect findings** as inline comments (severity badges, suggestion blocks)
- **Predictive warnings** in Check Run summary only — NOT as inline comments. Separate section: "Predictions: files that usually change together, missing tests." This prevents predictive noise from eroding trust in defect findings.
- Sensitive findings: redact in PR comment, full in audit log
- Submit atomically
- Write audit record

### 5.2 PR Review Pipeline (Phase 3+ additions, if graph justified)

Steps 1-3 and 7-8 remain identical. Changes:

**Step 4 becomes:** Query SurrealDB Code Semantic Graph (with PR overlay) instead of ad-hoc tree-sitter analysis. Richer: multi-hop traversals, historical review patterns, cross-repo edges (future).

**Step 4.5 (new):** PR Overlay — parse changed files, create temporary graph nodes/edges tagged with `overlay_key`. Merged with default-branch graph during queries. Cleanup after review.

**Step 5 adds:** Graph structural checks against SurrealDB (broken callers with N-hop traversal, type hierarchy violations, missing interface implementations).

### 5.3 PR Review Pipeline (Phase 4+ additions, if semantic retrieval justified)

**Step 4 adds:** Hybrid search (BM25 + HNSW vector) in SurrealDB, reranking, parent-child expansion.

**Layer 3 (complex PRs only):** LLM-driven agentic search with graph-backed tools. Complexity threshold trigger. Hard caps on iterations/tokens.

### 5.4 Workflow Orchestration

```python
# --- Business logic (no framework dependency) ---

async def sha_guard(pr: PrMetadata) -> bool:
    current = await github.get_pr(pr.repo_id, pr.pr_number)
    return current.head_sha == pr.head_sha

async def process_diff(pr: PrMetadata) -> ReviewRequest:
    mirror = get_mirror(pr.repo_id)
    diff = mirror.diff(pr.base_sha, pr.head_sha)
    return build_review_request(parse_and_extend(diff, mirror))

async def get_structural_context(req: ReviewRequest) -> StructuralContext:
    mirror = get_mirror(req.repo_id)
    return extract_context(mirror, req, head_sha=req.head_sha)

async def run_deterministic(req: ReviewRequest, ctx: StructuralContext) -> list[Finding]:
    return ast_grep_check(req) + structural_check(ctx) + predictive_check(ctx)

async def run_llm_review(req: ReviewRequest, ctx: StructuralContext,
                         deterministic: list[Finding]) -> list[Finding]:
    prompt = render_prompt(req, ctx, deterministic)
    return parse_llm_response(await litellm_call(prompt, select_model(req)))

async def score_evidence(findings: list[Finding], ctx: StructuralContext) -> list[Finding]:
    confirmed = confirm_against_structure(findings, ctx)
    remaining = [f for f in findings if f not in confirmed]
    scored = await self_reflect_batch(remaining)
    return confirmed + scored

async def publish(findings: list[Finding], pr: PrMetadata) -> ReviewResult:
    if not await sha_guard(pr):
        return ReviewResult(status="aborted", reason="stale_sha")
    defects = [f for f in findings if f.origin != "predictive" and f.publishable]
    predictions = [f for f in findings if f.origin == "predictive" and f.publishable]
    return await github_publish(pr, defects, predictions)

# --- Orchestration layer (DBOS, swappable) ---

@DBOS.step()
async def step_sha_guard(pr): return await sha_guard(pr)
@DBOS.step()
async def step_process_diff(pr): return await process_diff(pr)
@DBOS.step()
async def step_structural_context(req): return await get_structural_context(req)
@DBOS.step()
async def step_deterministic(req, ctx): return await run_deterministic(req, ctx)
@DBOS.step()
async def step_llm_review(req, ctx, det): return await run_llm_review(req, ctx, det)
@DBOS.step()
async def step_score(findings, ctx): return await score_evidence(findings, ctx)
@DBOS.step()
async def step_publish(findings, pr): return await publish(findings, pr)

@DBOS.workflow()
async def review_pr(pr: PrMetadata):
    if not await step_sha_guard(pr):
        return {"status": "aborted", "reason": "stale_sha"}
    req = await step_process_diff(pr)
    ctx = await step_structural_context(req)
    det = await step_deterministic(req, ctx)
    llm = await step_llm_review(req, ctx, det)
    scored = await step_score(det + llm, ctx)
    return await step_publish(scored, pr)
```

### 5.5 Indexing Pipeline (Phase 3+, if justified)

Only built if Bet A is proven and Layer 1 quality plateaus.

- Bare mirror as source (already exists from Phase 1)
- tree-sitter → SurrealDB graph nodes/edges
- Graph versioning: monotonic `index_version_id`, atomic swap on completion
- Reviews never read in-progress index
- NL enrichment + dual embedding + BM25 added in Phase 4

---

## 6. Signal Taxonomy

### 6.1 Signal Dimensions

| Dimension | Values | Description |
|-----------|--------|-------------|
| **origin** | `deterministic`, `structural`, `llm`, `predictive` | How the finding was produced. `structural` covers tree-sitter analysis (Phase 2) AND graph queries (Phase 3+) — one stable enum value across all phases. |
| **confidence** | `verified`, `high`, `medium`, `low` | How certain we are |
| **severity** | `critical`, `warning`, `suggestion` | How important to fix (one canonical enum) |
| **category** | `bug`, `security`, `breaking-change`, `performance`, `missing-test`, `co-change`, `stale-doc`, `style` | What kind |
| **publishability** | `publish`, `redact-and-publish`, `suppress`, `audit-only` | Whether/how to show it |

### 6.2 Confidence by Origin

| Origin | Typical Confidence | Expected FP Rate | Cost |
|--------|-------------------|-------------------|------|
| `deterministic` (AST-grep) | `verified` | < 1% | Free |
| `graph` (structural analysis) | `high` | < 5% | Free |
| `llm` + structural confirmation | `high` | < 10% | 1 LLM call |
| `llm` + self-reflection >= 7 | `medium` | 10-20% | 1 LLM + 1 batched call |
| `llm` + self-reflection < 7 | `low` | > 20% | 1 LLM + 1 batched call |
| `predictive` | `high` (statistical) | Depends on threshold | Free |

### 6.3 Publishing Rules

| Finding Type | Where Published | Why |
|-------------|----------------|-----|
| Defect findings (verified/high confidence) | Inline PR comments | Actionable, high signal |
| Defect findings (medium confidence) | Suppressed by default (opt-in) | Avoid noise |
| Defect findings (low confidence) | Suppressed, audit-only | FP risk too high |
| Predictive warnings (co-change, missing test, stale doc) | **Check Run summary section only** — NOT inline comments | Useful as awareness, but mixing with defects erodes trust |
| Sensitive findings | Redacted inline comment + full audit log | Never leak secrets |

### 6.4 Graph Extraction Accuracy Contract

Structural analysis quality varies by language. Explicit expectations:

| Language | Import Resolution | Call Graph | Type Hierarchy | Known Blind Spots |
|----------|------------------|-----------|----------------|-------------------|
| **Python** | High (static imports) | Medium (dynamic dispatch, decorators, metaclasses reduce accuracy) | Medium | Monkey-patching, `getattr`, `importlib`, runtime code generation |
| **TypeScript** | High | High (mostly static) | High | Dynamic imports, `eval`, reflection-heavy patterns |
| **Go** | High (explicit imports) | High (static dispatch) | High (interfaces explicit) | Code generation, `reflect` package |
| **Java** | High | Medium-High | High | Reflection, annotation processors, generated code |
| **Rust** | High | High | High (traits explicit) | Macro-generated code, `unsafe` blocks |

**Completeness flag:** Every structural context package carries `graph_completeness: full | partial | limited` per language. Findings that depend on incomplete graphs are downgraded in confidence.

---

## 7. GitHub Integration

### 7.1 GitHub App

**Permissions:** `pull_requests: write`, `checks: write`, `contents: read`, `metadata: read`

**Webhooks:** `pull_request` (opened, synchronize, reopened), `issue_comment` (slash commands)

**Webhook durability:** Every delivery persisted to `webhook_events` with `delivery_id` for idempotency and replay.

### 7.2 Publishing

- Pending review pattern: create PENDING → accumulate inline comments → submit atomically
- Check Run: summary with annotations (defect counts + predictive warnings section)
- Rate limits: 80/min, 500/hr content creation. Pending review batches. Prioritize by severity if near limit.

### 7.3 Slash Commands (MVP)

- `/kenjutsu review` — trigger full review
- `/kenjutsu review <file>` — review specific file
- `/kenjutsu ignore` — reply to a finding to suppress (stores fingerprint)

### 7.4 Debounce

On `synchronize`: timer resets per event. 30-60s quiet → enqueue. If review in-flight, cancel first.

---

## 8. Review Engine

### 8.1 Prompt Architecture

```text
System Prompt:
  - Role, output schema (Pydantic), severity/category definitions
  - Repo-specific rules from .kenjutsu.yaml
  - Prompt injection framing

Review Payload (delimited untrusted sections):
  - <pr_metadata>title, description</pr_metadata>
  - <diff>formatted hunks</diff>
  - <structural_context>imports, callers, co-changes</structural_context>
  - <deterministic_findings>already-found issues</deterministic_findings>
  - File tree

Output Schema:
  - findings[]: file, line_start, line_end, severity, category, description, suggestion
  - summary, risk_assessment
```

### 8.2 Model Selection

`complexity = file_count * 2 + line_count / 100 + file_type_weight + caller_count / 10`

| Score | Model |
|-------|-------|
| < 50 | Sonnet-class |
| >= 50 | Opus-class |

Self-reflection: different model family, batched. Fallback: primary → secondary → same-model.

### 8.3 Prompt Caching

System prompt + repo summary cached. Up to 90% input cost reduction.

### 8.4 PR-Agent Study Catalog

Mine git history for: prompt evolution, edge case handling, config surface, self-reflection patterns, diff edge cases, multi-language quirks. Seeds benchmark suite.

---

## 9. Configuration

`.kenjutsu.yaml` in repo root. Zero-config works.

```yaml
review:
  auto: true
  severity_threshold: warning
  confidence_threshold: high
  max_findings: 20
  predictive_warnings: true          # show in Check Run summary

ignore:
  paths:
    - "vendor/**"
    - "*.generated.go"
  categories:
    - "style"

models:
  primary: auto
```

Resolution: repo config > org defaults (future) > Kenjutsu defaults.

---

## 10. Data Model (PostgreSQL)

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `installations` | Tenants | `id`, `github_id`, `account_name`, `account_type`, `plan`, `settings_json`, `created_at` |
| `repos` | Enabled repos | `id`, `installation_id`, `github_id`, `full_name`, `default_branch`, `config_json`, `mirror_path`, `active_index_version` (null until Phase 3), `indexed_at` |
| `reviews` | One per run | `id`, `repo_id`, `pr_number`, `head_sha`, `base_sha`, `index_version_id` (null Phase 1-2), `context_source` (mirror/graph), `trigger`, `status` (queued/processing/complete/failed/superseded/aborted), `model_used`, `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms_json`, `findings_raw_count`, `findings_published_count`, `created_at` |
| `findings` | Individual findings | `id`, `review_id`, `fingerprint`, `file_path`, `line_start`, `line_end`, `origin`, `confidence`, `severity`, `category`, `publishability`, `description`, `suggestion`, `evidence_sources_json`, `published`, `github_comment_id` |
| `suppressions` | Ignored findings | `id`, `repo_id`, `fingerprint`, `suppressed_by`, `reason`, `created_at` |
| `webhook_events` | Raw log | `id`, `delivery_id` (unique), `installation_id`, `event_type`, `payload_json`, `processed`, `created_at` |
| `audit_log` | Immutable | `id`, `installation_id`, `repo_id`, `action`, `detail_json`, `created_at` |

**Tenant isolation:** All queries filter by `installation_id`. Reviews join through repos, which are scoped to installations. No cross-tenant data access by construction.

---

## 11. Multi-Tenancy and Pricing

### 11.1 Queue Fairness

- Per-tenant concurrency cap
- Per-tenant rate limiting
- Global LLM provider rate limiting
- Stale-work cancellation (superseded reviews cancelled)
- Per-tenant cost cap (alert at 80%, hard stop at 100%)

### 11.2 Pricing Tiers

| Tier | Target | Included | Price Signal |
|------|--------|----------|-------------|
| **Free** | Individual devs, OSS | N PRs/month, public repos, single model | $0 |
| **Pro** | Small teams | Higher PR limit, private repos, model selection, slash commands, predictive warnings | ~$19-29/seat/month |
| **Enterprise** | Regulated orgs | Unlimited, Layer 2/3 (when available), custom rules, audit export, SSO, SLA | Custom |

**Cost alignment:** Monitor COGS per tenant. If seat pricing doesn't cover LLM costs for high-volume tenants, introduce usage-aware adjustments (included PR budget per seat, overage pricing).

---

## 12. Audit and Governance

### 12.1 Audit Record

Every review: review_id, repo, PR, head_sha, base_sha, context_source (mirror/graph), index_version_id (if graph), model + version, tokens, cost, findings by origin/confidence/severity, published/suppressed counts, per-stage latency, graph_completeness per language.

### 12.2 Enterprise Features

- Audit log export (JSON, CSV)
- Review policy enforcement
- Required Check Run for branch protection
- Finding acknowledgment tracking
- Quality reporting (FP rate by confidence tier)

---

## 13. Authentication and Security

### 13.1 GitHub App Auth

RS256 JWT (10-min) → installation token (1-hour, refresh at 50min). HMAC-SHA256 webhook verification.

### 13.2 Secrets Management

MVP: environment variables. Production: cloud secrets manager with rotation.

### 13.3 Data Privacy

- Customer code sent to LLM providers — must be disclosed
- Embeddings/NL summaries (Phase 3+) are derived customer IP
- On uninstall: delete all tenant data within 24 hours
- Audit log retention: configurable, default 1 year

**Enterprise privacy note:** Finance/healthcare buyers will require: provider routing controls, zero-retention LLM agreements, BYO API keys, and potentially self-hosted LLM options. These are Phase 5+ features gated by customer demand. The spec does NOT claim enterprise-ready privacy posture at launch.

---

## 14. SurrealDB (Phase 3+, Evidence-Gated)

SurrealDB is NOT in the Phase 1-2 architecture. It is introduced only after Bet A is validated.

### 14.1 License Risk

SurrealDB uses **BSL 1.1** (Business Source License), not standard open source. Implications:
- Free to use as a database for your application
- Cannot offer SurrealDB itself as a competing managed database service
- License converts to Apache 2.0 after the change date
- Risk: terms could change. Monitor.

### 14.2 What It Provides (If Justified)

- Native graph traversal (multi-hop queries as one-liners vs recursive CTEs)
- Vector search (HNSW) + BM25 full-text in one engine
- PR overlay as tagged temporary nodes/edges
- Graph versioning with atomic version swap

### 14.3 Graph Schema

Nodes: `file`, `function`, `class`, `module`, `test`, `author`
Edges: `calls`, `imports`, `contains`, `inherits`, `implements`, `tested_by`, `co_changes`, `authored_by`

All carry `index_version_id`. PR overlay tagged with `overlay_key`.

### 14.4 PR Overlay Semantics

- Changed files parsed into temporary nodes/edges
- New functions get nodes; changed functions get updated nodes; deleted functions get tombstones
- Overlay has precedence over default-branch data for the same symbol
- Overlay is scoped to a single review workflow and cleaned up after
- Concurrent reviews on the same PR: each gets its own overlay (tagged by `head_sha`)
- Overlay does NOT persist across reviews

### 14.5 Deployment

| Phase | Mode |
|-------|------|
| Dev | Embedded (in-memory) |
| Phase 3 | Single-node container, persistent volume |
| Scale | Dedicated instance, automated backups |

Backup: daily export + rebuild from git (graph is derived data).
Schema: `.surql` files in repo, applied idempotently.

### 14.6 Escape Plan

**Trigger:** Data corruption, HNSW P99 > 100ms, graph traversal P99 > 500ms for 3-hop, critical bugs unfixed > 2 weeks, BSL license change, SDK instability.

**Path:** PostgreSQL + pgvector. Edges table with recursive CTEs. Multi-hop (>3) as materialized views.

**Loss:** Graph query expressiveness.
**Keep:** All functionality. Evidence taxonomy. Predictive analysis (from git log directly).

---

## 15. Repository Storage

### 15.1 Persistent Bare Mirrors

Each repo gets `git clone --bare`, stored on persistent volume. Updated via `git fetch` on webhook.

Provides: tree-sitter parsing, git log mining, diff generation, rename detection — all without GitHub API calls.

### 15.2 Large Monorepo Handling

- Partial clone with blob filter (`git clone --bare --filter=blob:limit=1m`) for repos > 1GB — fetch blobs on demand during parsing
- `git log` depth limited to 6 months or 10K commits
- Incremental analysis critical — never re-parse full repo per PR
- Storage monitoring with per-repo alerts

### 15.3 Cleanup

On uninstall: delete mirror, all findings, reviews, audit data. Target: 24 hours.

---

## 16. Performance Budgets

These are viability thresholds. If exceeded, the design needs simplification.

| Metric | Budget | Measured At |
|--------|--------|-------------|
| Review latency (typical PR, P50) | < 30 seconds | End-to-end, webhook to published review |
| Review latency (typical PR, P95) | < 60 seconds | End-to-end |
| Review latency (large PR, P95) | < 180 seconds | End-to-end |
| Structural context extraction | < 5 seconds | Step 4 |
| Mirror fetch (incremental) | < 10 seconds | git fetch on webhook |
| Index update (Phase 3+, incremental) | < 30 seconds | Changed files only |
| Graph traversal 3-hop (Phase 3+) | < 500ms P99 | SurrealDB query |
| HNSW ANN query (Phase 4+) | < 100ms P99 | SurrealDB vector search |
| Codebase scale (supported) | Up to 1M functions | Before requiring infra scaling |

---

## 17. Error Handling

| Failure | Behavior | Recovery |
|---------|----------|----------|
| GitHub API down | Retry (3x, exponential). If still failing: `failed` review, error Check Run. | Next event auto-retries. |
| LLM provider down | Fallback chain. All down: workflow pauses. | DBOS resumes from failed step. |
| SurrealDB unavailable (Phase 3+) | Fall back to tree-sitter-from-mirror (Phase 1-2 path). | SurrealDB recovery restores graph context. |
| Publishing fails | Retry publishing only. LLM results persisted. | No re-computation. |
| New commit mid-review | Cancel, debounce, re-enqueue. | Automatic. |
| Mirror fetch fails, head_sha present locally | Review proceeds — mirror has the code needed. | Next fetch updates mirror. |
| Mirror fetch fails, head_sha NOT present locally | Abort structural analysis. Degrade to diff-only LLM review with `context_freshness: degraded`. Never publish structural findings from stale state. | Next fetch updates mirror, next review gets full context. |
| Indexing fails (Phase 3+) | Previous complete version stays active. Partial run discarded. | Next merge triggers fresh run. |

---

## 18. Phase Plan

### Phase 1 — Foundation + Evaluation Harness

- GitHub App, webhook server (FastAPI), webhook persistence
- HMAC verification, debounce, sha guard
- Persistent bare mirror management
- GitHub provider: auth, diff, file retrieval, review publishing, Check Runs
- Diff processor: parsing, AST extension, token budgeting
- Config system: `.kenjutsu.yaml`
- Slash commands
- PostgreSQL schema + migrations
- Finding fingerprints (with normalization for stability)
- Idempotent publishing, stale review handling
- **Evaluation harness:** benchmark suite seeded from PR-Agent catalog. Known-bug PRs, known-FP PRs. Measure: comments per PR, accepted-finding rate, FP rate per confidence tier.
- **Milestone:** Receives webhooks, parses diffs, publishes placeholder reviews, measures quality baseline (diff-only).

### Phase 2 — Review Intelligence (Prove Bet A)

- LLM integration (LiteLLM), Jinja2 prompts, Pydantic output, prompt caching
- Prompt injection defense
- Sensitive finding detection + redaction
- Structural context from bare mirrors (tree-sitter imports, callers, co-change, test matching)
- Deterministic analysis: AST-grep (5 languages) + structural checks
- Predictive warnings (co-change, missing tests) — published in Check Run summary, NOT inline
- Evidence scoring: structural confirmation + cross-model self-reflection (batched)
- Signal taxonomy: origin, confidence, severity, category, publishability
- Audit logging
- Per-tenant queue fairness
- Graph completeness flag per language
- **Run evaluation harness against real PRs. Measure lift over diff-only baseline.**
- **Go/no-go for Bet B:** If structural context produces >15% accepted-finding lift AND graph-origin findings are >20% of accepted findings, proceed to Phase 3.
- **Milestone:** Reviews real PRs with structural context. Measurable quality metrics. Bet A validated or invalidated.

### Phase 3 — Code Semantic Graph (Prove Bet B, if justified)

- SurrealDB setup, graph schema
- Indexing pipeline: tree-sitter → SurrealDB nodes/edges
- Co-change edge computation
- Graph versioning: atomic swap, version GC
- PR overlay: temporary nodes/edges, precedence rules, cleanup
- Migrate structural context queries from ad-hoc tree-sitter to graph traversal
- Multi-hop queries (>3 levels) for blast radius analysis
- Pattern regression detection (previously-rejected patterns reintroduced)
- **A/B measurement:** tree-sitter-only (Phase 2) vs graph-backed (Phase 3) on evaluation harness
- **Go/no-go for Bet C:** If graph produces measurable quality lift AND Layer 1 quality plateaus, proceed to Phase 4.
- **Milestone:** Graph operational. Measurable improvement over tree-sitter-only.

### Phase 4 — Semantic Retrieval + Agentic Search (Prove Bet C, if justified)

- NL enrichment: Haiku-class summaries, content-hash keyed
- Dual embedding: Voyage-code-3 NL + raw code
- BM25 index with code-aware tokenization
- Hybrid retrieval: BM25 + HNSW, RRF fusion
- Reranking: Jina v2, Voyage Rerank 2.5
- Layer 3 agent: LLM search loop with graph tools, complexity triggering, cost caps
- **A/B measurement:** graph-only vs graph+semantic on evaluation harness
- **Milestone:** Full three-layer pipeline. Complex PRs get deep review. Measurable improvement over graph-only.

### Phase 5 — Production Hardening

- Prompt iteration across real PRs, multiple languages
- FP tracking per confidence tier, category, language
- Multi-tenant hardening: abuse prevention, cost caps
- Monitoring: latency, LLM errors, queue depth, mirror storage
- Feedback collection: accept/reject/ignore signals
- Uninstall cleanup pipeline
- Documentation
- **Milestone:** Production-ready. Measurable quality. Paying customers.

---

## 19. Cost Projections

### 19.1 Infrastructure (Monthly)

| Component | Phase 1-2 | Phase 3+ |
|-----------|-----------|----------|
| Webhook server + workers | $20-50 | $50-150 |
| PostgreSQL | $20-50 | $50-150 |
| SurrealDB | — | $50-200 |
| Repo mirror storage | $5-20 | $50-200 |
| Monitoring | $0-30 | $50-100 |
| **Total** | **$45-150** | **$250-800** |

### 19.2 LLM Cost Per Review

| PR Size | Model | Cost (no cache) | Cost (cached) |
|---------|-------|-----------------|---------------|
| Small | Sonnet | $0.14 | $0.06 |
| Typical | Sonnet | $0.32 | $0.12 |
| Large | Sonnet multi-pass | $1.28 | $0.45 |
| Complex | Opus | $1.75 | $0.65 |
| Self-reflection (batched) | GPT-5.4 | $0.10-0.25 | $0.05-0.10 |

### 19.3 Embedding/Indexing (Phase 4+)

| Scale | Functions | Embed Cost | NL Cost | Monthly Re-index (10% churn) |
|-------|-----------|-----------|---------|------------------------------|
| Small | 100K | $3.60 | $10 | $1.36 |
| Medium | 1M | $36 | $100 | $13.60 |
| Large | 10M | $360 | $1,000 | $136 |

---

## 20. Risk Assessment

### Risks We Accept

| Risk | Likelihood | Impact | Rationale |
|------|-----------|--------|-----------|
| Prompt engineering longer than expected | High | Medium | Empirical. Budget for it. PR-Agent catalog + eval harness from Phase 1. |
| SurrealDB maturity (Phase 3+) | Medium | Medium | Only introduced after Bet A proven. Escape plan defined. Graph is derived data. BSL 1.1 license monitored. |
| FP rate above target initially | High | Medium | Signal taxonomy makes threshold tunable. Ship conservative (high confidence only). |
| Dynamic language blind spots | High | Low | Explicit per-language accuracy contract. Completeness flag downgrades confidence. |

### Risks We Mitigate

| Risk | Mitigation |
|------|-----------|
| LLM reliability | Cross-provider fallback. Step-level retry. |
| SurrealDB instability | Graph behind interface. PostgreSQL escape hatch. Only introduced Phase 3. |
| DBOS lock-in | Business logic is framework-free. Thin orchestration wrapper. |
| Stale reviews | Sha guard before AND after processing. Workflow cancellation. |
| Prompt injection | Input isolation, output validation, finding sanitization. |
| Cost runaway | Per-tenant caps, rate limiting, Layer 3 iteration budgets. |
| Graph produces no value | Go/no-go gate after Phase 2. Don't build Phase 3 if metrics don't justify. |

### Risks We Avoid

| Risk | How |
|------|-----|
| AGPL contamination | Build from scratch. |
| Over-engineering at launch | Phase 1-2 is bare mirrors + tree-sitter + one LLM. No graph, no embeddings. |
| Embedding vendor lock-in | Dual: Voyage + Nomic (Apache 2.0). Phase 4+ only. |
| Predictive noise eroding trust | Predictions in Check Run summary, not inline. Separate from defects. |
| Enterprise privacy overclaim | Spec explicitly notes privacy posture is not enterprise-ready at launch. |

---

## Appendix A: PR-Agent Study Guide

Mine git history (patterns only, no code):
1. Prompt evolution (TOML changes)
2. Edge case handling (issues, bug fixes)
3. Configuration surface
4. Self-reflection patterns
5. Diff edge cases (binary files, renames, merge commits)
6. Multi-language quirks

## Appendix B: Embedding Model Selection (Phase 4+)

**Primary:** Voyage-code-3 — 92.28% suite, 32K context, 1024d, Matryoshka + INT8. $0.18/1M tokens.
**Fallback:** Nomic Embed Code — Apache 2.0, near-Voyage quality, self-hostable.
**Short-doc reranker:** Jina Reranker v2 — CodeSearchNet 71.36, 278M params.
**Long-doc reranker:** Voyage Rerank 2.5 — 32K context, $0.05/1M tokens.

## Appendix C: Competitive Positioning

| Capability | CodeRabbit | Greptile | PR-Agent | Kenjutsu |
|-----------|-----------|---------|---------|----------|
| Context | Diff-only | Full index | Diff-only | Structural from mirrors (Phase 1-2), graph (Phase 3+) |
| FP approach | Volume | Catch rate | Basic | Evidence taxonomy + signal dimensions |
| Branch consistency | Unknown | Unknown | None | Sha guard + structural parsing at head_sha (Phase 1-2), PR overlay (Phase 3+) |
| Predictive | No | No | No | Co-change, missing tests, stale docs |
| Governance | No | No | No | Full audit, evidence provenance |

## Appendix D: Evaluation Metrics

| Metric | Target | Measured From |
|--------|--------|---------------|
| Comments per PR (defects only) | < 8 average | Published findings count |
| Accepted-finding rate | > 60% | Accept/dismiss/ignore signals |
| FP rate (verified) | < 1% | Manual audit |
| FP rate (high confidence) | < 10% | Manual audit + feedback |
| Predictive warning action rate | > 30% | User behavior tracking |
| Stale-comment rate | 0% | Sha guard prevents |
| Review latency (P50) | < 30s | Pipeline instrumentation |
| Review latency (P95) | < 60s | Pipeline instrumentation |
| Uninstall rate (first week) | < 20% | Tenant lifecycle |

## Appendix E: Evaluation Contract

This contract defines how Bet A is measured. It must be frozen before Phase 2 evaluation begins.

### What counts as "accepted"

| Signal | Classification | Source |
|--------|---------------|--------|
| Author resolves the review comment thread | **Accepted** | GitHub API — comment thread `isResolved` |
| Author changes code in the area the finding identified | **Accepted** | Diff analysis between review sha and next commit |
| Author dismisses or reacts negatively | **Rejected** | `/kenjutsu reject` slash command or dismiss action |
| No response within 48 hours | **Ignored** | Timer-based, excluded from accepted-finding rate calculation |

### What counts as a false positive

A finding is a false positive if:
- The finding is factually wrong (the code doesn't have the issue described)
- The finding is correct but not actionable (team convention allows it)
- The finding is a duplicate of another finding in the same review

A finding is NOT a false positive if:
- The author disagrees but the finding is technically correct
- The finding is low severity and the author chooses not to fix it

### Experiment protocol for Bet A

- **One primary model** (Claude Sonnet) — no multi-provider routing during experiment
- **One fixed prompt family** — no prompt changes during experiment runs
- **One benchmark corpus** (50+ PRs, TypeScript/JavaScript + Python)
- **Two variants:** diff-only baseline vs structural-context variant
- **Blind comparison:** same corpus, same model, same prompt, only context differs
- **Metric:** accepted-finding rate lift, FP rate per confidence tier, latency delta
- **Freeze period:** no prompt or model changes during the evaluation window

### Feedback collection (Phase 2, not Phase 5)

Lightweight feedback signals must be collectible before Bet A evaluation:
- `/kenjutsu accept` — explicit positive signal on a finding
- `/kenjutsu reject` — explicit negative signal
- GitHub comment thread resolution — implicit accept
- These signals are stored per finding fingerprint for FP rate tracking

## Appendix F: Open Questions (Resolve During Phase 1)

1. **Fingerprint normalization** — exact canonicalization rules for LLM output to ensure stable fingerprints across reruns
2. **Rename/move handling** — how fingerprints, structural context, and diff mapping handle file renames
3. **Secret detection implementation** — regex, entropy, external scanner, or combination?
4. **Co-change probability threshold** — what probability triggers a warning? Needs calibration on real repos.
5. ~~**Evaluation labeling**~~ — RESOLVED: see Appendix E Evaluation Contract
6. ~~**First paying customer identity**~~ — RESOLVED: mid-size teams (10-50 devs), private GitHub Cloud, TypeScript/JavaScript + Python
