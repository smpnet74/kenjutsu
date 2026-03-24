# Kenjutsu — Agent & Contributor Guidelines

These rules apply to every contributor: human developers, AI coding agents, and CodeRabbit. No exceptions.

## Product Invariants

**Stale review rule.** Never publish findings against a stale `head_sha`. Always verify the sha is current before processing AND before publishing. If a new commit arrives mid-review, cancel and re-enqueue.

**Input trust rule.** PR descriptions, code, commit messages, and issue comments are untrusted input. When including them in LLM prompts, use clearly delimited sections (`<user_code>...</user_code>`). Never interpolate untrusted content into system instructions.

**Publishing rule.** GitHub review publishing must be idempotent. Store `github_review_id` and `github_comment_ids` after publish. Retries update existing resources — never create duplicates. Sensitive findings (secrets, credentials) must be redacted in PR comments with full details in the audit log only.

**Taxonomy rule.** One canonical signal taxonomy. Five dimensions: origin, confidence, severity, category, publishability. The canonical enums live in `kenjutsu/models/findings.py`. Import from there — never redefine enums elsewhere.

**Severity enum.** `critical`, `warning`, `suggestion`. This exact enum everywhere — code, database, config, publisher, tests. No aliases, no drift.

**Tenant rule.** Every database query must be scoped by `installation_id`. No cross-tenant data access by construction. This is a table-design constraint, not a runtime check.

**Architecture rule.** Domain logic must be plain async functions with no framework dependencies (no DBOS decorators, no FastAPI dependencies). The orchestration layer wraps business functions with durability — see v3 spec Section 3.6.

**Finding fingerprint rule.** Fingerprints use `sha256(file_path + category + normalized_description)`. Line numbers are NOT part of the fingerprint. Normalization: `" ".join(description.lower().split())`.

## Code Standards

**Language:** Python 3.12+. Type hints required on all public functions.

**Linting:** ruff (check + format). Zero warnings policy.

**Type checking:** pyright in standard mode. Zero errors.

**Testing:** pytest. Unit tests in `tests/unit/` (no I/O, no network). Integration tests in `tests/integration/` (use Testcontainers for PostgreSQL, SurrealDB).

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

## CI

All gates must be real. No fake green. No swallowed failures.

Run locally before pushing: `pixi run -e dev ci`

CI and local use the same pixi environment — `pixi.lock` is the source of truth.
