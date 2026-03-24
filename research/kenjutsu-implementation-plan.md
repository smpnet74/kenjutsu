# Kenjutsu Implementation Plan — Issue Hierarchy for Demeter

> **For the Demeter agent team:** This plan maps directly to Paperclip issues. Each Phase is a Goal. Each numbered item is an Issue (assigned to a lead). Each lettered sub-item is a Sub-Issue (assigned to an IC). The CEO creates the Goals and top-level Issues, then delegates decomposition to the Chief Architect and Engineering Manager per the delivery process.

**Goal:** Build Kenjutsu, an AI-powered PR review SaaS product, following the v3 architecture spec.

**Architecture Spec:** `research/kenjutsu-architecture-v3.md` (in the Kenjutsu repo)

**Product Repo:** https://github.com/smpnet74/kenjutsu

---

## Repo State (as of scaffold merge)

**READ THIS BEFORE STARTING WORK.** The repo is not empty. The following has already been built, tested, reviewed by CodeRabbit, and merged to `main`.

### What exists

| Component | Status | Location |
|-----------|--------|----------|
| Pixi workspace (Python 3.12, conda-forge) | Done | `pyproject.toml`, `pixi.lock` |
| CI pipeline (7 quality gates + ci-pass aggregate) with path filtering | Done | `.github/workflows/ci.yml` |
| CodeRabbit config (15 path instructions, 3 custom checks) | Done | `.coderabbit.yaml` |
| FastAPI entry point with `/health` endpoint | Done | `kenjutsu/app.py` |
| Finding model with 5-dimension signal taxonomy | Done | `kenjutsu/models/findings.py` |
| Signal taxonomy enums (Origin, Confidence, Severity, Category, Publishability) | Done | `kenjutsu/models/findings.py` |
| Finding fingerprints (stable, case/whitespace insensitive) | Done | `kenjutsu/models/findings.py` |
| 16 unit tests covering taxonomy and fingerprint behavior | Done | `tests/unit/test_models.py` |
| Dockerfile (multi-stage, health check) | Done | `Dockerfile` |
| Architecture spec v3 | Done | `research/kenjutsu-architecture-v3.md` |
| Implementation plan | Done | `research/kenjutsu-implementation-plan.md` |

### Package structure (follow this layout)

The CodeRabbit config has path-specific review instructions for each of these modules. **New code must go in the matching directory** so CodeRabbit applies the correct review guidance.

```text
kenjutsu/
  app.py              # FastAPI entry point (exists)
  models/
    __init__.py        # Exports Finding + enums (exists)
    findings.py        # Signal taxonomy + fingerprints (exists)
  server/              # Webhook reception, HMAC verification, debounce
  github/              # GitHub App auth, API client, review publishing
  pipeline/            # Review pipeline steps, sha guard, workflow orchestration
  context/             # Structural context extraction (tree-sitter, imports, callers)
  analysis/            # Deterministic analysis (AST-grep patterns, structural checks)
  review/              # LLM review engine, prompt templates, structured output
  evidence/            # Evidence scoring, cross-model self-reflection
  publisher/           # GitHub review/Check Run publishing, redaction
  config/              # .kenjutsu.yaml parsing, defaults
  db/                  # PostgreSQL schema, Alembic migrations
  mirror/              # Bare mirror management (clone, fetch, diff, read)
tests/
  unit/                # Fast, no network, no DB
    test_models.py     # Signal taxonomy tests (exists, 16 tests)
  integration/         # Requires PostgreSQL
    test_placeholder.py # Placeholder (exists, replace with real tests)
```

### CI gates (already enforced)

| Gate | Runs When | Tool |
|------|-----------|------|
| Lint | Code changes | ruff check + format |
| Type check | Code changes | pyright |
| Security | Code changes | bandit + pip-audit |
| Unit tests | Code changes | pytest tests/unit/ |
| Integration tests | Code changes | pytest tests/integration/ (Testcontainers spins up PostgreSQL, SurrealDB Phase 3+) |
| Coverage | Tests run | coverage threshold (80% target) |
| Docker build | Dockerfile or app code changes | docker build |
| ci-pass | Always | Aggregates all triggered gates |

Non-code PRs (research/, docs/, .md files) skip heavy gates automatically.

### Testing strategy

Tests bring their own infrastructure via **Testcontainers**. Integration tests spin up real PostgreSQL (and SurrealDB in Phase 3+) as Docker containers inside the test run. No manual database setup required — same behavior locally and in CI.

| Test layer | Directory | Infrastructure | When to use |
|-----------|-----------|---------------|-------------|
| Unit | `tests/unit/` | None — pure logic | All business logic, models, parsing |
| Integration | `tests/integration/` | Testcontainers (PostgreSQL, SurrealDB Phase 3+) | DB operations, webhook handling, full pipeline |
| E2E | `tests/e2e/` (future) | Testcontainers + GitHub API mock | Full review cycle |

**Fixture pattern:** Use `@pytest.fixture(scope="session")` with Testcontainers context managers in `tests/conftest.py`. See v3 spec Section 3.5 for code examples.

**Important:** When adding new services, add a Testcontainers fixture — do NOT add CI `services:` blocks. Tests own their infrastructure.

### Pixi tasks (use these, not raw commands)

```bash
pixi run -e dev lint          # ruff check + format check
pixi run -e dev format        # auto-format
pixi run -e dev typecheck     # pyright
pixi run -e dev test          # unit tests
pixi run -e dev test-integration  # integration tests
pixi run -e dev test-all      # all tests with coverage
pixi run -e dev security      # bandit
pixi run -e dev ci            # all gates
pixi run serve                # start FastAPI dev server
```

---

## Merge and Flow Rules

**READ THIS FIRST. These rules govern when work ships and when work stops.**

### Default Rule: Merge on Green

When a sub-issue's acceptance criteria pass and tests are green, **merge it immediately.** Do not wait for:
- Other sub-issues in the same issue to complete
- The parent issue to be "ready"
- Permission from a lead or the board
- The full phase to be done

**If the acceptance criteria pass, the PR is green, and the review process is complete — merge and move on to the next sub-issue.** Work that sits idle waiting for approval is wasted time.

### Issue Completion

An issue (parent) is complete when all its sub-issues are merged and the issue-level acceptance criteria are met. The assignee marks it done and moves on. No ceremony.

### Phase Flow

Phases flow continuously unless there is an explicit **HARD GATE** marker. Here is the complete gate map:

| Transition | Gate Type | Rule |
|-----------|-----------|------|
| Phase 1 → Phase 2 | **No gate.** | Begin Phase 2 sub-issues as soon as their Phase 1 dependencies are merged. Do NOT wait for all of Phase 1 to complete. If the webhook server is merged and the diff processor is merged, the LLM review engine can start even if the evaluation harness isn't done yet. |
| Phase 2 → Phase 3 | **HARD GATE.** | STOP. Do not begin any Phase 3 work until issue 2.8 (Bet A Validation) is complete and the Chief Architect has issued a written go/no-go decision approved by the CEO. If the decision is "no-go," Phase 3 does not start. |
| Phase 3 → Phase 4 | **HARD GATE.** | STOP. Do not begin any Phase 4 work until issue 3.4 (Bet B Validation) is complete with a written go/no-go decision approved by the CEO. |
| Phase 4 → Phase 5 | **No gate.** | Begin Phase 5 work as soon as Phase 4 sub-issues start landing. Production hardening can overlap with late Phase 4 work. |

### Parallel Work Within a Phase

Sub-issues that don't depend on each other should be worked in parallel. The Engineering Manager assigns based on dependency order. Examples:
- Phase 1: Mirror management (1.3) can parallel with diff processor (1.4) and webhook server (1.2)
- Phase 2: Structural context (2.3) can parallel with LLM review engine (2.5) and deterministic analysis (2.4)

### What "Merge on Green" Does NOT Mean

- It does NOT mean skip code review. Follow the delivery process review routing matrix.
- It does NOT mean skip tests. Acceptance criteria include tests passing.
- It does NOT mean merge broken code. Green means CI passes, review approved, acceptance criteria met.
- It does NOT mean ignore the HARD GATES. Phase 3 and Phase 4 require explicit go/no-go decisions with data.

---

## Phase 1 — Foundation + Evaluation Harness

**Goal:** Stand up the core infrastructure: GitHub App, webhook pipeline, diff processing, bare mirrors, trust mechanics, evaluation harness, and a staging environment to test against real webhooks.

**Milestone:** Receives webhooks, parses diffs, publishes placeholder reviews, measures quality baseline. Staging auto-deploys on merge to main.

**Flow:** No gate into Phase 2. Start Phase 2 work as soon as dependencies are merged. Merge each sub-issue as it passes acceptance criteria. Phase 2 real-world evaluation depends on staging (1.11) being deployed.

---

### 1.1 Project Scaffolding and Repo Setup

**Assigned to:** Engineering Manager → DevOps Engineer
**Priority:** Critical (blocks everything)

Set up the Kenjutsu repo with the Python project structure, CI pipeline, and deployment foundation.

**Sub-issues:**

**a) Initialize Python project structure — COMPLETE**
~~Assigned to: DevOps Engineer~~
- ~~Initialize pixi workspace with Python 3.12+, FastAPI, pytest~~
- ~~Create package structure, add `.gitignore`, `pixi.lock`~~
- ~~Add `Dockerfile` with multi-stage build and health check~~
- ~~Acceptance: `pixi run serve` starts FastAPI on localhost, `pixi run -e dev test` runs 16 tests green~~
- **Done.** Merged in PR #17. FastAPI app at `kenjutsu/app.py`, Finding model at `kenjutsu/models/findings.py`, 16 passing tests.

**b) PostgreSQL schema and migrations**
Assigned to: Senior Engineer A (Backend)
- Create initial schema: `installations`, `repos`, `reviews`, `findings`, `suppressions`, `webhook_events`, `audit_log`
- Use Alembic for migrations within the existing pixi workspace (`pixi add alembic psycopg sqlalchemy` when starting this issue)
- Add `testcontainers[postgres]` to dev dependencies
- Create `tests/conftest.py` with `postgres_url` session fixture using Testcontainers (see v3 spec Section 3.5)
- Write migration integration tests that run `alembic upgrade head` against the Testcontainers PostgreSQL
- All tables include `installation_id` scoping per v3 spec Section 10
- Place migration code in `kenjutsu/db/` (matches CodeRabbit path instruction)
- Acceptance: `alembic upgrade head` runs clean against Testcontainers PostgreSQL, schema matches spec, works identically local and CI

**c) CI pipeline — COMPLETE**
~~Assigned to: DevOps Engineer~~
- ~~CI: 7 quality gates (lint, type check, security, unit tests, integration tests, coverage, Docker build) + ci-pass aggregate~~
- ~~Path filtering: non-code PRs skip heavy gates~~
- ~~CodeRabbit config with 15 path instructions and 3 custom pre-merge checks~~
- ~~Branch protection: require ci-pass job~~
- **Done.** Merged in PR #16 and #17. Validated through 3 rounds of CodeRabbit review.

---

### 1.2 GitHub App Integration

**Assigned to:** Engineering Manager → Senior Engineer A
**Priority:** Critical

Implement GitHub App registration, authentication, and webhook handling.

**Sub-issues:**

**a) GitHub App authentication**
Assigned to: Senior Engineer A
- RS256 JWT generation from App private key (10-min lifetime)
- Installation access token flow (1-hour, proactive refresh at 50min)
- Token caching per installation
- Ref: v3 spec Section 13.1
- Acceptance: Can authenticate as any installation and call GitHub API successfully

**b) Webhook server**
Assigned to: Senior Engineer A
- FastAPI POST `/webhook` endpoint
- HMAC-SHA256 signature verification — reject on failure, no exceptions
- Persist raw webhook to `webhook_events` table with `delivery_id` for idempotency
- Event routing: `pull_request` (opened, synchronize, reopened), `issue_comment`
- Return 200 within 500ms
- Ref: v3 spec Section 5.1 Step 1
- Acceptance: Receives test webhook from GitHub, persists it, routes correctly. Rejects invalid signatures.

**c) Debounce logic**
Assigned to: Senior Engineer A
- On `synchronize` events, timer resets on each new event
- After 30-60s of quiet, enqueue the review workflow
- If review in-flight for same PR, cancel it first
- Ref: v3 spec Section 7.4
- Acceptance: Rapid-fire pushes result in single review enqueue after quiet period

**d) Slash command parsing**
Assigned to: Senior Engineer D (Tooling)
- Parse `issue_comment` webhooks for `/kenjutsu review`, `/kenjutsu review <file>`, `/kenjutsu ignore`
- `/kenjutsu ignore` extracts the finding fingerprint from the parent comment
- Enqueue appropriate workflow or store suppression
- Ref: v3 spec Section 7.3
- Acceptance: Each command triggers correct action. Invalid commands are silently ignored.

---

### 1.3 Persistent Bare Mirror Management

**Assigned to:** Engineering Manager → Senior Engineer C (Infrastructure)
**Priority:** Critical

Manage persistent bare clones of each repo for reliable parsing and history mining.

**Sub-issues:**

**a) Mirror lifecycle**
Assigned to: Senior Engineer C
- On repo install: `git clone --bare` to persistent volume
- On webhook: `git fetch` to update
- On uninstall: delete mirror and all associated data
- Large repos (>1GB): sparse checkout for initial clone
- Storage monitoring with per-repo alerts
- Ref: v3 spec Section 15
- Acceptance: Install triggers clone, webhook triggers fetch, uninstall cleans up. Can diff any two shas after fetch.

**b) Mirror API**
Assigned to: Senior Engineer C
- Internal Python API: `get_mirror(repo_id)`, `mirror.diff(base_sha, head_sha)`, `mirror.read_file(path, sha)`, `mirror.git_log(path, limit)`
- Thread-safe (multiple workers may read concurrently, fetch is serialized per repo)
- Acceptance: API works correctly with concurrent readers, fetch doesn't corrupt state

---

### 1.4 Diff Processor

**Assigned to:** Engineering Manager → Senior Engineer A
**Priority:** Critical

Parse PR diffs into structured objects with AST-extended context.

**Sub-issues:**

**a) Unified diff parser**
Assigned to: Senior Engineer A
- Parse unified diff output into structured `PatchFile` objects (file path, hunks, line numbers, additions, deletions)
- Convert to decoupled hunk format (separate new/old views with line numbers)
- Deletion omission: strip deletion-only hunks, list deleted files by name
- Acceptance: Parses real-world diffs from 5+ open source repos correctly

**b) tree-sitter AST context extension**
Assigned to: Senior Engineer A
- For each hunk, use tree-sitter to find the enclosing function/class
- Extend hunk to include the full enclosing scope
- Support 5 first-class languages: Python, TypeScript/JavaScript, Go, Java, Rust
- Acceptance: Hunks in the middle of a function are extended to show the full function. Works for all 5 languages.

**c) Token budget management**
Assigned to: Senior Engineer A
- Count tokens using LiteLLM `token_counter` (model-aware)
- Greedy fill within model context limit, prioritized: changed files > imported files > co-changed files
- Multi-pass mode: if total exceeds budget, split into chunks for parallel LLM calls
- Reserve 10% for output buffer
- Acceptance: Never exceeds model context. Multi-pass triggers correctly on large diffs.

---

### 1.5 Workflow Orchestration

**Assigned to:** Engineering Manager → Senior Engineer D (Tooling)
**Priority:** High

Implement the DBOS-backed workflow pipeline with abstraction boundary.

**Sub-issues:**

**a) Orchestration abstraction layer**
Assigned to: Senior Engineer D
- Business logic as plain async functions (no DBOS imports)
- Thin `step_*` wrapper layer that adds DBOS durability
- Workflow composition in a separate module
- Per v3 spec Section 3.5: if DBOS is replaced, only wrappers change
- Acceptance: Business functions are importable and testable without DBOS. Wrappers add durability.

**b) Review workflow**
Assigned to: Senior Engineer D
- Implement full pipeline: sha_guard → process_diff → structural_context → deterministic_analysis → llm_review → evidence_scorer → publisher
- Each step is a `@DBOS.step()` wrapper around the business function
- Failure at any step resumes from that step, not the beginning
- Acceptance: Workflow runs end-to-end. Kill mid-step, restart, resumes from failed step.

**c) Queue management**
Assigned to: Senior Engineer D
- Global review queue with concurrency limit
- Per-tenant queues with concurrency cap and rate limiting
- Stale-work cancellation: if new sha arrives for same PR, cancel in-flight workflow
- Per-tenant cost cap (alert at 80%, hard stop at 100%)
- Ref: v3 spec Section 11.1
- Acceptance: Two tenants can't starve each other. Stale reviews are cancelled. Cost cap prevents runaway.

---

### 1.6 Trust Mechanics

**Assigned to:** Chief Architect → Senior Engineer A + Senior Engineer D
**Priority:** Critical

Implement the core trust guarantees that make the system safe to publish.

**Sub-issues:**

**a) Sha guard**
Assigned to: Senior Engineer A
- Before processing: fetch PR from GitHub API, verify `head_sha` matches
- Before publishing: re-check `head_sha`, abort if stale
- Ref: v3 spec Section 4.2
- Acceptance: Stale sha detected → review aborted, not published. Tested with simulated mid-review push.

**b) Finding fingerprints — PARTIALLY COMPLETE**
Assigned to: Senior Engineer D
- Core implementation exists in `kenjutsu/models/findings.py` — `sha256(file_path + category + normalized_description)`, case/whitespace insensitive, line numbers excluded. 6 unit tests passing.
- **Remaining work:** Add `code_context_hash` to the fingerprint (currently uses description only). This improves stability when LLM rephrases the same finding differently.
- Ref: v3 spec Section 4.3
- Acceptance: Same finding on same code produces same fingerprint even if LLM rewords the description.

**c) Idempotent publishing**
Assigned to: Senior Engineer A
- Check for existing review for `(pr_number, head_sha)` before creating
- Store `github_review_id` and `github_comment_ids` after publish
- Retries update existing, not create duplicates
- Ref: v3 spec Section 4.5
- Acceptance: Publishing the same review twice doesn't create duplicate comments.

**d) Supersession**
Assigned to: Senior Engineer D
- One canonical review per `(repo_id, pr_number, head_sha)`
- New review marks previous as `superseded`
- Ref: v3 spec Section 4.1, 4.4
- Acceptance: Force push → old review superseded, new review created.

---

### 1.7 Configuration System

**Assigned to:** Engineering Manager → Senior Engineer D
**Priority:** Medium

**Sub-issues:**

**a) .kenjutsu.yaml parser**
Assigned to: Senior Engineer D
- Parse `.kenjutsu.yaml` from repo root (via bare mirror at head_sha)
- Pydantic model with defaults for all fields
- Resolution: repo config > Kenjutsu defaults
- Ref: v3 spec Section 9
- Acceptance: Missing file → all defaults work. Partial file → specified values override defaults.

---

### 1.8 GitHub Publisher

**Assigned to:** Engineering Manager → Senior Engineer A
**Priority:** High

**Sub-issues:**

**a) Pending review publisher**
Assigned to: Senior Engineer A
- Create pending review → accumulate inline comments → submit atomically
- Inline comments at correct file/line with severity badges
- Suggestion blocks using GitHub's ` ```suggestion ` syntax
- Rate limit awareness: monitor `X-RateLimit-Remaining`, prioritize by severity near limit
- Ref: v3 spec Section 7.2
- Acceptance: Review appears as single notification with all comments. Suggestions are one-click applicable.

**b) Check Run publisher**
Assigned to: Senior Engineer A
- Create Check Run at pipeline start (`in_progress`)
- Update with annotations (batched, 50 per call)
- Complete: `success` / `neutral` / `failure` based on findings
- Predictive warnings in Check Run summary section (NOT inline comments)
- Ref: v3 spec Section 7.2, 6.3
- Acceptance: Check Run visible on PR. Predictive warnings appear in summary only.

**c) Audit logging**
Assigned to: Senior Engineer A
- Write immutable audit record on every review completion
- Fields per v3 spec Section 12.1: model, tokens, cost, findings by origin/confidence/severity, latency breakdown
- Acceptance: Every review (including aborted/failed) has an audit record.

---

### 1.9 Evaluation Harness

**Assigned to:** Chief Architect → QA Engineer + Research Specialist
**Priority:** Critical (blocks Bet A validation)

Build the measurement infrastructure that proves or disproves the product thesis.

**Sub-issues:**

**a) Benchmark PR corpus**
Assigned to: Research Specialist
- Collect 50+ real-world PRs across 5+ repos (mix of small/medium/large, refactor/feature/bugfix)
- Annotate: known bugs in the diff, known false positive patterns, expected findings
- Seed from PR-Agent prompt catalog (mine git history for edge cases)
- Acceptance: Corpus covers all 5 first-class languages, includes at least 10 refactor/API-change PRs

**b) Evaluation runner**
Assigned to: QA Engineer
- Run Kenjutsu review pipeline against each benchmark PR
- Record: findings produced (by origin, confidence, severity), latency, tokens, cost
- Compare against human-annotated expected findings
- Calculate: accepted-finding rate, FP rate per confidence tier, comments per PR
- Ref: v3 spec Appendix D
- Acceptance: Can run full benchmark suite, produces metrics dashboard / report

**c) Diff-only baseline**
Assigned to: QA Engineer
- Run the same LLM with diff-only context (no structural analysis) against the benchmark corpus
- This is the control group for measuring Bet A
- Acceptance: Baseline metrics recorded for comparison against Phase 2 results

---

### 1.10 PR-Agent Study Catalog

**Assigned to:** Chief Architect → Research Specialist
**Priority:** High

**Sub-issues:**

**a) Prompt evolution catalog**
Assigned to: Research Specialist
- Mine PR-Agent git history for prompt TOML changes over time
- Catalog: what was tuned, what was added/removed, why (from commit messages/issues)
- Document self-reflection scoring patterns
- Ref: v3 spec Appendix A
- Acceptance: Structured document covering prompt evolution, edge cases, config surface. Feeds into review engine prompt design in Phase 2.

---

### 1.11 Staging Environment

**Assigned to:** Engineering Manager → DevOps Engineer
**Priority:** High (blocks Phase 2 real-world evaluation)

Deploy a staging environment so the team can test against real GitHub webhooks before Phase 2 evaluation.

**Sub-issues:**

**a) Register staging GitHub App**
Assigned to: DevOps Engineer
- Register a separate GitHub App for staging (not the future production App)
- Permissions: `pull_requests: write`, `checks: write`, `contents: read`, `metadata: read`
- Webhook URL: `https://staging.kenjutsu.dev/webhook` (or equivalent)
- Install on 2-3 test repos controlled by the team
- Store App private key and webhook secret in GitHub Environment `staging`
- Acceptance: Staging App receives webhooks from test repos.

**b) Staging deployment workflow**
Assigned to: DevOps Engineer
- `.github/workflows/deploy-staging.yml`: merge to main → deploy to Railway/Fly/ECS
- Uses GitHub Environment `staging` for secrets (`DATABASE_URL`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`, LLM API keys)
- Deployment only triggers after `ci-pass` succeeds
- Health check: deployment waits for `/health` endpoint to return 200
- Acceptance: Merge to main auto-deploys. Staging receives webhooks within 5 minutes of merge.

**c) Staging PostgreSQL**
Assigned to: DevOps Engineer
- Managed PostgreSQL instance (smallest tier, Railway/Supabase/Neon)
- Run Alembic migrations on deploy
- Acceptance: Staging app connects to staging DB. Migrations run on deploy.

**d) Staging smoke test**
Assigned to: QA Engineer
- After each staging deploy, trigger a PR on a test repo and verify:
  - Webhook received
  - Pipeline runs (or placeholder response)
  - Check Run created on the PR
- Can be manual initially, automated later
- Acceptance: Staging deploy verified working after each merge to main.

**Note on environments:**

| Environment | Trigger | GitHub App | Database | Purpose |
|------------|---------|-----------|----------|---------|
| **Local dev** | `pixi run serve` | None (mock/test fixtures) | Testcontainers | Development |
| **CI** | PR to main | None | Testcontainers | Automated testing |
| **Staging** | Merge to main | Staging App (test repos) | Managed PostgreSQL | Real-world validation, Phase 2 evaluation |
| **Production** (Phase 5) | Release tag (`v*`) | Production App (customer repos) | Managed PostgreSQL (backups, HA) | Customer-facing |

Two separate GitHub Apps are required — staging and production. Same code, different credentials. This prevents staging bugs from affecting customer repos.

---

## Phase 2 — Review Intelligence (Prove Bet A)

**Goal:** Build the full review pipeline: LLM integration, structural context, deterministic analysis, evidence scoring, and predictive warnings. Run against evaluation harness to validate Bet A.

**Milestone:** Reviews real PRs with structural context. Measurable quality metrics. Bet A validated or invalidated.

**Flow:** Merge each sub-issue as it passes acceptance criteria. Start Phase 2 sub-issues as soon as their Phase 1 dependencies are merged — do NOT wait for all of Phase 1.

**HARD GATE at end of Phase 2:** After issue 2.8 (Bet A Validation) completes, ALL Phase 3 work is blocked until the Chief Architect issues a written go/no-go decision approved by the CEO. Criteria: >15% accepted-finding lift on refactor/API/security PRs AND >20% of accepted findings from structural/graph sources. If no-go, Phase 3 does not start — the team pivots to optimizing Phases 1-2.

---

### 2.1 Architecture Spec Decomposition

**Assigned to:** Chief Architect → Technical Planner A
**Priority:** Critical (blocks all Phase 2 implementation)

Produce detailed technical specs for each Phase 2 component. These specs become the implementation reference for engineers.

**Sub-issues:**

**a) Structural context extractor spec**
Assigned to: Technical Planner A
- Detail: how imports are resolved per language (5 languages), how callers are found, co-change mining parameters, test matching heuristics
- Include the graph extraction accuracy contract from v3 spec Section 6.4
- Document known blind spots per language
- Acceptance: Chief Architect approves. Engineers can implement from this spec without ambiguity.

**b) Deterministic analysis rules spec**
Assigned to: Technical Planner A
- Catalog: AST-grep patterns per language, structural checks (removed params, changed returns, removed exports)
- Scope explicitly per v3 spec: NOT a type checker, catches syntactic structural breakage only
- Acceptance: Chief Architect approves.

**c) Review engine and prompt spec**
Assigned to: Technical Planner A
- Prompt template structure (Jinja2), output schema (Pydantic), model selection logic (complexity scoring formula)
- Prompt injection defense framing
- Sensitive finding detection approach (regex + entropy)
- Self-reflection batching strategy
- Incorporate learnings from PR-Agent study catalog (1.10)
- Acceptance: Chief Architect approves.

---

### 2.2 Implementation Planning

**Assigned to:** Engineering Manager → Technical Planner B
**Priority:** Critical (blocks implementation)

Decompose the approved specs into engineer-ready issues with acceptance criteria.

**Sub-issues:**

**a) Phase 2 issue decomposition**
Assigned to: Technical Planner B
- Break each spec from 2.1 into implementation issues assigned to specific engineers
- Each issue has: acceptance criteria, test plan, dependencies
- Sequence: structural context and deterministic analysis can parallel with LLM integration
- Acceptance: Engineering Manager approves. All Phase 2 work has clear owners and sequencing.

---

### 2.3 Structural Context Extractor

**Assigned to:** Engineering Manager → Senior Engineer A + Senior Engineer B
**Priority:** Critical

Extract structural context from bare mirrors using tree-sitter.

**Sub-issues:**

**a) Import graph extraction**
Assigned to: Senior Engineer A
- Parse changed files with tree-sitter, extract import statements
- Resolve imports to files in the repo (per-language resolution rules)
- Reverse imports: scan repo for files that import the changed files
- 5 first-class languages
- Acceptance: Given a changed file, returns its imports and reverse imports correctly for all 5 languages.

**b) Caller/callee extraction**
Assigned to: Senior Engineer B
- Parse changed files, extract function/method definitions and call sites
- For each changed function, find callers in other files (via reverse import + AST scan)
- `graph_completeness` flag per language (full for Go/Rust/Java, partial for Python/JS)
- Acceptance: Given a changed function, returns callers. Completeness flag accurate per language.

**c) Co-change analysis**
Assigned to: Senior Engineer A
- Mine `git log` from bare mirror: files that historically change together
- Compute co-change probability (Jaccard similarity over commit history)
- Limit: 6 months or 10K commits depth
- Output: co-change pairs with probability scores
- Acceptance: Returns co-change pairs for changed files with reasonable probability thresholds.

**d) Test file matching**
Assigned to: Senior Engineer B
- Path heuristics: `foo.py` → `test_foo.py`, `foo.ts` → `foo.test.ts`, `foo.spec.ts`, etc.
- Per-language conventions
- Acceptance: Correctly matches test files for all 5 languages.

**e) Context package assembly**
Assigned to: Senior Engineer A
- Combine: import graph, callers, co-change, test matches, enclosing scopes
- All parsed from `head_sha` in bare mirror (branch-consistent)
- Token-budget aware: trim context to fit within model limits
- Output: structured `StructuralContext` object
- Acceptance: Context package includes all signals, fits token budget, parses from correct sha.

---

### 2.4 Deterministic Analysis Engine

**Assigned to:** Engineering Manager → Senior Engineer B + Security Engineer
**Priority:** High

**Sub-issues:**

**a) AST-grep rule engine**
Assigned to: Senior Engineer B
- Pattern matching framework using tree-sitter queries
- Initial rules per language (from spec in 2.1b): hardcoded credentials, SQL injection, unreachable code
- Findings tagged: `origin: deterministic`, `confidence: verified`
- Acceptance: Detects known patterns in benchmark corpus with <1% FP rate.

**b) Structural breakage checks**
Assigned to: Senior Engineer B
- Using data from structural context extractor (2.3):
  - Removed function params still passed by callers
  - Changed return types
  - Removed exports still imported elsewhere
- Findings tagged: `origin: graph`, `confidence: high`
- Acceptance: Detects structural breakage in benchmark corpus.

**c) Security-specific patterns**
Assigned to: Security Engineer
- Sensitive finding detection: regex patterns + entropy analysis for secrets/credentials/API keys
- OWASP-derived patterns per language
- Findings tagged with `publishability: redact-and-publish` when sensitive
- Acceptance: Detects hardcoded secrets in test cases. Redaction works correctly.

**d) Predictive warnings**
Assigned to: Senior Engineer A
- Co-change warnings: PR modifies A but not B where probability > threshold
- Missing test warnings: new/changed functions with no matching test
- Tagged: `origin: predictive`, `confidence: high`
- Published in Check Run summary only (NOT inline)
- Acceptance: Warnings fire correctly on benchmark PRs. Appear in Check Run summary, not inline.

---

### 2.5 LLM Review Engine

**Assigned to:** Engineering Manager → Senior Engineer D + Senior Engineer A
**Priority:** Critical

**Sub-issues:**

**a) LiteLLM integration**
Assigned to: Senior Engineer D
- Multi-provider setup: Claude, GPT-5.4, Gemini, GLM
- Model selection by complexity score (formula from v3 spec Section 8.2)
- Fallback chain: primary → secondary → tertiary
- Prompt caching configuration
- Acceptance: Can call all configured providers. Fallback triggers on provider failure.

**b) Prompt templates**
Assigned to: Senior Engineer D
- Jinja2 templates per v3 spec Section 8.1
- System prompt with role, output schema, severity/category definitions, prompt injection framing
- Review payload with delimited untrusted sections
- Incorporate PR-Agent study catalog learnings
- Acceptance: Renders correct prompt for small/medium/large PRs. Deterministic findings included in prompt.

**c) Structured output parser**
Assigned to: Senior Engineer D
- Pydantic schema for LLM response: findings[], summary, risk_assessment
- YAML/JSON parsing with repair logic for malformed output
- Validation: reject findings with invalid file paths or line numbers
- Acceptance: Parses valid output correctly. Repairs common malformation. Rejects garbage.

**d) Multi-pass review**
Assigned to: Senior Engineer A
- Split large diffs into chunks within token budget
- Each chunk reviewed independently with shared context
- Deduplicate findings across chunks (by fingerprint)
- Synthesis pass merges into coherent review
- Acceptance: Large PR (50+ files) produces deduplicated, coherent review across chunks.

---

### 2.6 Evidence Scoring

**Assigned to:** Engineering Manager → Senior Engineer D
**Priority:** High

**Sub-issues:**

**a) Structural confirmation**
Assigned to: Senior Engineer D
- For each LLM finding, check if structural context data supports it
- E.g.: LLM says "this return type change breaks callers" → structural context confirms callers exist → `confidence: high`
- Acceptance: LLM findings with structural backing are correctly elevated.

**b) Cross-model self-reflection**
Assigned to: Senior Engineer D
- Batch all unconfirmed findings into single self-reflection call
- Use different model family than reviewer (Claude reviewed → GPT scores, etc.)
- Score >= 7 → `confidence: medium`, < 7 → `confidence: low` (suppressed)
- Fallback chain: primary scorer → secondary → same-model
- Acceptance: Self-reflection correctly filters findings. Batching keeps cost down. Fallback works.

**c) Meta-synthesis**
Assigned to: Senior Engineer D
- Merge deterministic + LLM + predictive findings
- Deduplicate by fingerprint
- Apply publishability rules (redact sensitive findings)
- Rank by severity, produce coherent narrative for the review summary
- Acceptance: Final finding set is deduplicated, correctly ordered, sensitive findings redacted.

---

### 2.7 Signal Taxonomy Implementation — PARTIALLY COMPLETE

**Assigned to:** Engineering Manager → Senior Engineer D
**Priority:** High

**a) Finding model — COMPLETE**
~~Assigned to: Senior Engineer D~~
- ~~Pydantic model with all 5 dimensions: origin, confidence, severity, category, publishability~~
- ~~One canonical severity enum (`critical`, `warning`, `suggestion`) used everywhere~~
- **Done.** `kenjutsu/models/findings.py` has all 5 enums + Finding model + computed fingerprint. 16 unit tests covering enum values, model creation, fingerprint stability.
- **Remaining work:** Verify enum consistency when publisher, DB schema, and config modules are built. Those modules must import from `kenjutsu.models` — do NOT redefine enums elsewhere.

---

### 2.8 Bet A Validation

**Assigned to:** Chief Architect + QA Engineer
**Priority:** Critical (gates Phase 3)

**Sub-issues:**

**a) Run evaluation harness with structural context**
Assigned to: QA Engineer
- Run full benchmark corpus with structural context enabled
- Compare against diff-only baseline from 1.9c
- Compute: accepted-finding rate lift, graph-origin finding share, FP rate per tier, latency impact
- Ref: v3 spec Section 2 go/no-go criteria
- Acceptance: Data produced, results reported to Chief Architect and CEO.

**b) Go/no-go decision**
Assigned to: Chief Architect
- Evaluate metrics against thresholds:
  - >15% accepted-finding lift on refactor/API/security PRs → proceed
  - >20% of accepted findings from structural/graph sources → proceed
  - Otherwise → simplify, do not start Phase 3
- Decision documented with data
- Acceptance: Written go/no-go decision with supporting metrics. CEO approves.

---

### 2.9 Quality Assurance

**Assigned to:** Engineering Manager → QA Engineer
**Priority:** High

**Sub-issues:**

**a) Integration test suite**
Assigned to: QA Engineer
- All integration tests use Testcontainers — PostgreSQL spun up via `postgres_url` fixture in `tests/conftest.py`. No CI `services:` blocks.
- Integration boundary tests: webhook → pipeline → publisher flow using GitHub API contract fixtures/mocks (no live GitHub dependency in CI — live smoke tests run in staging per Issue 1.11)
- Edge cases: large PRs, binary files, empty diffs, force pushes, concurrent webhooks
- Trust mechanic tests: sha guard, supersession, idempotent publishing, debounce
- Acceptance: Full test suite green locally and in CI with identical behavior. Edge cases handled correctly.

**b) Security review**
Assigned to: Security Engineer
- HMAC verification cannot be bypassed
- Prompt injection defense validated (adversarial PR descriptions/code)
- Sensitive finding redaction works
- No secrets in logs or published comments
- Acceptance: Security review passed. No critical findings.

---

### 2.10 Documentation

**Assigned to:** Engineering Manager → Technical Writer
**Priority:** Medium

**Sub-issues:**

**a) Configuration reference**
Assigned to: Technical Writer
- Document all `.kenjutsu.yaml` options with defaults and examples
- Acceptance: Complete, accurate, matches implementation.

**b) Getting started guide**
Assigned to: Technical Writer
- Install the GitHub App, get first review, customize config
- Acceptance: A new user can follow the guide and get a review on their first PR.

---

## Phase 3 — Code Semantic Graph (Prove Bet B, if justified)

**Goal:** Introduce SurrealDB as the Code Semantic Graph. Migrate structural context from ad-hoc tree-sitter to persistent graph. Add PR overlay, graph versioning, multi-hop queries, pattern regression detection.

**Prerequisite:** Phase 2 HARD GATE passed. Chief Architect go decision with CEO approval. Do not start ANY Phase 3 sub-issue without this.

**Milestone:** Graph operational. Measurable improvement over tree-sitter-only.

**Flow:** Once the gate is cleared, merge each sub-issue as it passes acceptance criteria.

**HARD GATE at end of Phase 3:** After issue 3.4 (Bet B Validation) completes, ALL Phase 4 work is blocked until the Chief Architect issues a written go/no-go decision approved by the CEO. If no-go, Phase 4 does not start.

---

### 3.1 SurrealDB Architecture Spec

**Assigned to:** Chief Architect → Technical Planner A
**Priority:** Critical

**Sub-issues:**

**a) Graph schema design**
Assigned to: Technical Planner A
- Detail node types, edge types, indexes per v3 spec Section 6
- PR overlay semantics: creation, precedence, cleanup, concurrent review isolation
- Graph versioning: index_version_id, atomic swap, garbage collection
- Tenant isolation model (shared namespace with filters vs hard isolation)
- BSL 1.1 license implications documented
- Acceptance: Chief Architect approves. Schema covers all structural/temporal signals.

**b) Migration plan**
Assigned to: Technical Planner A
- How structural context queries migrate from bare-mirror tree-sitter to SurrealDB graph
- What changes in the pipeline (Step 4 becomes graph query, Step 4.5 adds overlay)
- Performance budget validation plan (P99 thresholds from v3 spec Section 16)
- Acceptance: Chief Architect approves.

---

### 3.2 SurrealDB Integration

**Assigned to:** Engineering Manager → Senior Engineer C + Senior Engineer A
**Priority:** Critical

**Sub-issues:**

**a) SurrealDB setup and deployment**
Assigned to: Senior Engineer C
- Docker container with persistent volume for production
- Python SDK integration
- Connection management, health checks
- Schema applied from `.surql` files on deploy
- Add Testcontainers `surrealdb_url` session fixture to `tests/conftest.py` using `DockerContainer("surrealdb/surrealdb:v2")` (see v3 spec Section 3.5)
- All SurrealDB integration tests use the Testcontainers fixture — no manual SurrealDB setup required
- Acceptance: SurrealDB running in production, integration tests pass locally and in CI identically via Testcontainers.

**b) Indexing pipeline**
Assigned to: Senior Engineer A
- tree-sitter → SurrealDB nodes (files, functions, classes, modules, tests) and edges (calls, imports, contains, inherits, tested_by)
- Co-change edge computation from git log → SurrealDB
- All tagged with `index_version_id`
- Incremental: content-hash, only re-process changed chunks
- Acceptance: Full index of test repo. Incremental update < 30s on typical PR.

**c) Graph versioning**
Assigned to: Senior Engineer C
- Monotonic `index_version_id`
- Active version stored in PostgreSQL `repos.active_index_version`
- Atomic swap only after indexing completes
- Old versions garbage-collected (configurable retention, default 3)
- Reviews record which version they used
- Acceptance: Reviews never read in-progress index. Version swap is atomic.

**d) PR overlay**
Assigned to: Senior Engineer A
- Parse changed files, create temporary nodes/edges tagged with `overlay_key`
- Overlay has precedence over default-branch data for same symbol
- Deleted functions get tombstone markers
- Concurrent reviews get separate overlays (tagged by `head_sha`)
- Cleanup after review completes or cancels
- Acceptance: New functions in PR are visible in graph queries. Cleanup verified.

**e) Migrate structural context to graph queries**
Assigned to: Senior Engineer A
- Replace bare-mirror ad-hoc tree-sitter calls with SurrealDB graph traversals
- Import graph, callers, co-change, test matching — all via SurrealQL
- Multi-hop queries (>3 levels) for blast radius analysis
- Acceptance: Same structural context, now from graph. Multi-hop works. Performance within budget.

---

### 3.3 Pattern Regression Detection

**Assigned to:** Engineering Manager → Senior Engineer B
**Priority:** Medium

- Track `reviewed_as` edges: finding → function, with verdict (accepted/rejected)
- When similar code pattern appears in new PR, check if it was previously rejected
- Flag: "This pattern was rejected in review X — was reintroduction intentional?"
- Acceptance: Previously-rejected pattern flagged when reintroduced.

---

### 3.4 Bet B Validation

**Assigned to:** Chief Architect + QA Engineer
**Priority:** Critical (gates Phase 4)

**a) A/B measurement**
Assigned to: QA Engineer
- Run benchmark corpus with tree-sitter-only (Phase 2) vs graph-backed (Phase 3)
- Compare: accepted-finding rate, FP rate, latency, multi-hop finding quality
- Acceptance: Data produced, reported.

**b) Go/no-go decision**
Assigned to: Chief Architect
- Graph produces measurable quality lift → proceed to Phase 4
- Quality flat → defer Phase 4, optimize Phase 2/3
- Acceptance: Written decision with data. CEO approves.

---

## Phase 4 — Semantic Retrieval + Agentic Search (Prove Bet C, if justified)

**Goal:** Add embedding-based semantic retrieval, hybrid search, reranking, and LLM-driven agentic search for complex PRs.

**Prerequisite:** Phase 3 HARD GATE passed. Chief Architect go decision with CEO approval. Do not start ANY Phase 4 sub-issue without this.

**Milestone:** Full three-layer pipeline. Complex PRs get deep review.

**Flow:** Once the gate is cleared, merge each sub-issue as it passes acceptance criteria. Phase 5 work can begin overlapping with late Phase 4.

---

### 4.1 Semantic Retrieval Spec

**Assigned to:** Chief Architect → Technical Planner A
**Priority:** Critical

- NL enrichment pipeline design
- Dual embedding strategy (NL summary + raw code)
- Hybrid search: BM25 + HNSW, RRF fusion
- Reranking strategy (Jina v2 + Voyage Rerank 2.5)
- Layer 3 agent tool belt design, complexity triggering, cost caps
- Acceptance: Chief Architect approves.

---

### 4.2 NL Enrichment Pipeline

**Assigned to:** Engineering Manager → Senior Engineer A
**Priority:** High

- LLM-generated NL summary per function/class chunk (Haiku-class)
- Content-hash keyed — skip unchanged
- Dual embedding: Voyage-code-3 for NL summaries + raw code
- Store both in SurrealDB HNSW index
- Acceptance: All functions/classes in test repo have NL summaries and dual embeddings.

---

### 4.3 Hybrid Retrieval

**Assigned to:** Engineering Manager → Senior Engineer A + Senior Engineer B
**Priority:** High

**a) BM25 index**
Assigned to: Senior Engineer B
- Code-aware tokenization: camelCase splitting, snake_case splitting
- SurrealDB native full-text index
- Acceptance: Identifier search returns correct results.

**b) Hybrid search + RRF fusion**
Assigned to: Senior Engineer A
- BM25 + HNSW vector search, merged via RRF (k=60)
- Rerank top-50 via Jina Reranker v2 (short docs) / Voyage Rerank 2.5 (long docs)
- Parent-child expansion: function match → return enclosing class/file
- Acceptance: Hybrid search returns higher quality results than either alone. Reranking measurably improves precision.

---

### 4.4 Layer 3 Agentic Search

**Assigned to:** Engineering Manager → Senior Engineer D
**Priority:** Medium

- LLM-driven search loop with tool belt: `search_code`, `read_file`, `find_references`, `find_tests`, `git_history`
- All tools backed by SurrealDB graph queries
- Complexity score threshold for triggering
- Hard caps: max iterations, max tokens consumed per search
- Acceptance: Complex PRs get deeper context. Agent terminates within budget. Layer 3 findings measurably improve quality.

---

### 4.5 Bet C Validation

**Assigned to:** Chief Architect + QA Engineer
**Priority:** Critical

- A/B: graph-only (Phase 3) vs graph+semantic (Phase 4) on benchmark corpus
- Measure: quality lift, cost increase, latency impact
- Go/no-go: quality justifies the cost and complexity
- Acceptance: Written decision with data.

---

## Phase 5 — Production Hardening

**Goal:** Make the system production-ready for paying customers. Prompt tuning, monitoring, feedback collection, documentation.

**Milestone:** Production-ready. Measurable quality. Ready for paying customers.

**Flow:** No gate. Begin as soon as Phase 4 sub-issues start landing (or immediately after Phase 2 if Phase 3/4 are deferred). Merge each sub-issue as it passes acceptance criteria.

---

### 5.1 Prompt Engineering Iteration

**Assigned to:** Chief Architect → Senior Engineer D + Research Specialist
**Priority:** Critical

- Iterate prompts on real-world PRs across all 5 languages
- Tune severity thresholds, self-reflection scoring
- Measure FP rate per confidence tier, category, language
- Target: <1% FP for verified, <10% for high confidence
- Acceptance: FP rates at or below targets on real-world PRs.

---

### 5.2 Monitoring and Observability

**Assigned to:** Engineering Manager → DevOps Engineer
**Priority:** High

- Structured logging (JSON)
- Metrics: review latency (P50/P95), LLM error rates, queue depth, mirror storage
- Alerting: latency spikes, provider failures, cost cap warnings, SurrealDB health (Phase 3+)
- Acceptance: Dashboard showing all key metrics. Alerts fire correctly.

---

### 5.3 Multi-Tenant Hardening

**Assigned to:** Engineering Manager → Senior Engineer C + Security Engineer
**Priority:** High

**a) Abuse prevention**
Assigned to: Senior Engineer C
- Rate limiting per installation
- Webhook flood protection
- Acceptance: Simulated abuse doesn't impact other tenants.

**b) Security hardening**
Assigned to: Security Engineer
- Full security review of production system
- Dependency audit
- Penetration testing of webhook endpoint
- Acceptance: Security review passed.

---

### 5.4 Feedback Collection

**Assigned to:** Engineering Manager → Senior Engineer B
**Priority:** High

- Track accept/dismiss/ignore signals per finding
- Store per fingerprint for FP rate measurement
- Future: use acceptance data to tune confidence thresholds per repo
- Acceptance: Feedback signals collected and queryable.

---

### 5.5 Uninstall Cleanup

**Assigned to:** Engineering Manager → Senior Engineer C
**Priority:** Medium

- On GitHub App uninstall: delete all tenant data
- Bare mirror, graph nodes/edges, reviews, findings, audit log, embeddings
- Target: complete within 24 hours
- Acceptance: Uninstall leaves no tenant data behind.

---

### 5.6 Production Deployment

**Assigned to:** Engineering Manager → DevOps Engineer
**Priority:** Critical

**Sub-issues:**

**a) Register production GitHub App**
Assigned to: DevOps Engineer
- Separate App from staging (different credentials, different webhook URL)
- Production webhook URL: `https://api.kenjutsu.dev/webhook`
- Store credentials in GitHub Environment `production` with required reviewers
- Acceptance: Production App registered, credentials secured.

**b) Production deployment workflow**
Assigned to: DevOps Engineer
- `.github/workflows/deploy-production.yml`: release tag (`v*`) → deploy to production
- Uses GitHub Environment `production` (requires manual approval before deploy)
- Run migrations, health check, rollback on failure
- Acceptance: Tagging `v0.1.0` deploys to production after approval. Rollback works.

**c) Production PostgreSQL**
Assigned to: DevOps Engineer
- Managed PostgreSQL with automated backups, point-in-time recovery
- Separate from staging — no shared data
- Acceptance: Production DB provisioned, backups verified, connection tested.

**d) Production monitoring**
Assigned to: DevOps Engineer
- Health check monitoring (uptime)
- Error alerting (webhook failures, LLM errors, publishing failures)
- Cost tracking per tenant
- Acceptance: Alerts fire on test failures. Dashboard shows key metrics.

---

### 5.7 Documentation

**Assigned to:** Engineering Manager → Technical Writer
**Priority:** High

**a) API documentation**
Assigned to: Technical Writer

**b) Operations runbook**
Assigned to: Technical Writer

**c) Updated getting started guide**
Assigned to: Technical Writer

- Acceptance: Complete, accurate, reviewed by Engineering Manager.
