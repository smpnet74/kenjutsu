# Kenjutsu — Agent & Contributor Guidelines

These rules apply to every contributor: human developers, AI coding agents, and CodeRabbit. No exceptions.

## Product Invariants

**Stale review rule.** Never publish findings against a stale `head_sha`. Always verify the sha is current before processing AND before publishing. If a new commit arrives mid-review, cancel and re-enqueue.

**Input trust rule.** PR descriptions, code, commit messages, and issue comments are untrusted input. When including them in LLM prompts, escape or strip any delimiter-like sequences (e.g., `</user_code>`) from the content BEFORE placing it in delimited sections (`<user_code>...</user_code>`). Never interpolate untrusted content into system instructions.

**Publishing rule.** GitHub review publishing must be idempotent. Store `github_review_id` and `github_comment_ids` after publish. Retries update existing resources — never create duplicates. Sensitive findings (secrets, credentials) must be redacted in PR comments with full details in the audit log only.

**Taxonomy rule.** One canonical signal taxonomy. Five dimensions: origin, confidence, severity, category, publishability. The canonical enums live in `kenjutsu/models/findings.py`. Import from there — never redefine enums elsewhere.

**Severity enum.** `critical`, `warning`, `suggestion`. This exact enum everywhere — code, database, config, publisher, tests. No aliases, no drift.

**Tenant rule.** Every database query must be scoped by `installation_id`. No cross-tenant data access by construction. This is a table-design constraint, not a runtime check.

**Architecture rule.** Domain logic must be plain async functions with no framework dependencies (no DBOS decorators, no FastAPI dependencies). The orchestration layer wraps business functions with durability — see v3 spec Section 3.6.

**Finding fingerprint rule.** Fingerprints use `sha256(f"{file_path}:{category}:{normalized_description}")` with colon separators to prevent concatenation ambiguity. Line numbers are NOT part of the fingerprint. Normalization: `" ".join(description.lower().split())`. See `kenjutsu/models/findings.py` for the canonical implementation.

## Code Standards

**Language:** Python 3.12+. Type hints required on all public functions.

**Linting:** ruff (check + format). Zero warnings policy.

**Type checking:** pyright in standard mode. Zero errors.

**Testing:** pytest. See Testing Discipline section below.

**Commits:** Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`).

**Dependencies:** Add via `pyproject.toml`. Run `pixi install` to regenerate `pixi.lock`. Never install packages outside pixi.

## Module Layout

New code must go in the matching directory — CodeRabbit applies path-specific review instructions based on this structure:

| Directory | Responsibility |
|-----------|---------------|
| `kenjutsu/app.py` | FastAPI entry point |
| `kenjutsu/models/` | Pydantic models, signal taxonomy, enums |
| `kenjutsu/server/` | Webhook reception, HMAC verification, debounce |
| `kenjutsu/github/` | GitHub App auth, API client |
| `kenjutsu/pipeline/` | Review pipeline steps, sha guard, orchestration |
| `kenjutsu/context/` | Structural context extraction (tree-sitter) |
| `kenjutsu/analysis/` | Deterministic analysis (AST-grep, structural checks) |
| `kenjutsu/review/` | LLM review engine, prompt templates |
| `kenjutsu/evidence/` | Evidence scoring, cross-model self-reflection |
| `kenjutsu/publisher/` | GitHub review/Check Run publishing, redaction |
| `kenjutsu/config/` | .kenjutsu.yaml parsing, defaults |
| `kenjutsu/db/` | PostgreSQL schema, Alembic migrations |
| `kenjutsu/mirror/` | Bare mirror management |

## Testing Discipline

These rules are non-negotiable. Every PR must follow them.

### The Rule

**Every PR that changes behavior must include tests that verify the changed behavior.** This is not optional. If you change code, you test the change. If you fix a bug, the test reproduces the bug before the fix and passes after. If you add a feature, the test verifies the feature works.

### Test Layers

| Layer | Location | Infrastructure | What belongs here |
|-------|----------|---------------|-------------------|
| **Unit** | `tests/unit/` | None — pure logic, no I/O, no network | Business logic, models, parsing, fingerprinting, token budgeting, config resolution |
| **Integration** | `tests/integration/` | Testcontainers (PostgreSQL, SurrealDB Phase 3+) | DB operations, webhook handling, pipeline steps with real DB, publishing idempotency |
| **E2E** | `tests/e2e/` (future) | Testcontainers + GitHub API mock | Full review cycle: webhook → pipeline → published review |

### What Must Be Tested

**Trust mechanics are safety-critical.** Every trust mechanic from the Product Invariants section must have integration tests:

- Sha guard: stale sha detected → review aborted, not published
- Idempotent publishing: same review published twice → no duplicate comments
- Finding fingerprints: same finding produces same fingerprint across reruns
- Supersession: new sha → old review marked superseded
- Debounce: rapid pushes → single review enqueued
- Sensitive redaction: secrets never appear in published comments
- Tenant isolation: queries never return cross-tenant data

**Boundary contracts need integration tests.** Every external boundary needs contract tests that verify integration behavior. Use real services via Testcontainers where available (PostgreSQL, SurrealDB). For non-containerized third-party services (GitHub API, LLM providers), use stable contract fixtures or recorded HTTP mocks plus periodic live smoke checks in staging.

**Deterministic analysis needs regression tests.** Every AST-grep pattern and structural check needs a test with a code sample that triggers it and a test with code that doesn't.

### What Does NOT Need Tests

- Config files (`.kenjutsu.yaml`, `pyproject.toml`) — validated by the parser, not by dedicated tests
- Prompt template text — the LLM output is nondeterministic; test the parsing and validation, not the generation
- CI workflow YAML — validated by actionlint, not pytest

### Regression Rule

**Bug fix PRs must include a test that fails before the fix and passes after.** This test lives permanently in the test suite and prevents the bug from returning. No exceptions.

### Coverage

Coverage is measured per-PR on changed files, not as a global percentage. The goal is not a number — it's confidence that changed behavior is verified. CI will enforce a minimum threshold on changed files once the test suite reaches critical mass (Issue 1.1b).

### Evaluation Harness (Phase 2+)

The evaluation harness measures review quality, not code correctness. It is a regression suite for the product's core promise (precision).

- **Baseline:** diff-only LLM review scores (established in Phase 1)
- **Gate:** review quality scores (accepted-finding rate, FP rate per confidence tier) must not regress between releases
- **Enforcement:** automated comparison against baseline in CI (Phase 2 Issue 2.8)

Quality regression is as serious as code regression. If a prompt change drops the accepted-finding rate, it doesn't ship.

## CI

All gates must be real. No fake green. No swallowed failures.

Run locally before pushing: `pixi run -e dev ci`

CI and local use the same pixi environment — `pixi.lock` is the source of truth.
