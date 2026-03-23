# GitHub Integration Options for AI Code Review

- **Status:** review
- **Author:** Chief Architect
- **Date:** 2026-03-23
- **Issue:** DEM-107
- **Parent:** DEM-104

---

## Executive Summary

For an AI code review tool, a **GitHub App** is the recommended primary integration — it offers the highest rate limits, exclusive Checks API access, a professional bot identity, and marketplace distribution. A **GitHub Action** should be offered as a secondary, zero-infrastructure alternative. Raw webhooks are not recommended for production.

---

## 1. Integration Models Compared

### GitHub App

A first-class GitHub integration that operates as an independent bot identity. Installed at the org/account level — users click "Install," select repos, and approve permissions. No per-repo config files needed.

**Authentication:** Two-phase token flow:
1. Generate a JWT (RS256-signed, app private key, 10-min max lifetime)
2. Exchange JWT for an installation access token (`POST /app/installations/{id}/access_tokens`, 1-hour expiry)
3. Token can be scoped to specific repos (up to 500) and permissions

**Rate limits:** 5,000 req/hr base, scaling +50/repo (>20) and +50/user (>20), capped at 12,500/hr. Enterprise Cloud: 15,000/hr.

**Exclusive capabilities:**
- Full write access to the Checks API (annotations, check runs, rich status output)
- Dedicated bot identity (`@your-app[bot]`)
- Single webhook endpoint for all installed repos
- GitHub Marketplace listing

**Trade-offs:**
- Requires hosting infrastructure for webhook receiver
- JWT/token management adds implementation complexity
- Tokens expire hourly (must refresh)

### GitHub Action

Runs as a workflow step inside GitHub's hosted runner infrastructure. Users add a YAML workflow file to each repo.

**Authentication:** `GITHUB_TOKEN` auto-provisioned per workflow run. Permissions declared in YAML — specifying any scope sets all unspecified scopes to `none`.

**Rate limits:** 1,000 req/hr per repository (significantly lower than Apps). Enterprise Cloud: 15,000/hr.

**Trade-offs:**
- Zero hosting infrastructure needed
- Simple per-repo setup (add YAML file)
- No token management
- But: per-repo workflow file (doesn't scale to hundreds of repos without automation)
- Cannot create Check Runs (read-only for non-App tokens)
- Consumes Actions minutes (cost at scale)
- Comments appear from generic `github-actions[bot]`, no custom identity

### Raw Webhooks

Manual webhook configuration per repo/org. Uses PATs or OAuth tokens for API access.

**Not recommended.** Does not scale, no marketplace presence, broad token scopes, manual setup per repo.

### Decision Matrix

| Criterion | GitHub App | GitHub Action | Raw Webhooks |
|---|---|---|---|
| Hosting required | Yes | No | Yes |
| Per-repo setup | No | Yes (YAML) | Yes (webhook) |
| Rate limit (base) | 5,000-12,500/hr | 1,000/hr | 5,000/hr (PAT) |
| Checks API write | Yes | No | No |
| Bot identity | Dedicated | github-actions[bot] | User identity |
| Marketplace | Yes | Yes | No |
| Permissions | Fine-grained | Workflow-scoped | Token-scoped |
| Installation UX | One-click | Commit YAML to repo | Manual config |

### What Existing Tools Use

- **CodeRabbit:** GitHub App (cloud SaaS). Permissions: read-write on code, commit statuses, issues, PRs; read-only on actions, checks, discussions, members.
- **PR-Agent / Qodo Merge:** Both. GitHub Action as the easy/free path; GitHub App for self-hosted production deployments.
- **Pattern:** App as primary recommended path, Action as self-hosted alternative.

---

## 2. Pull Request Review API

### Creating a Review

`POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews`

```json
{
  "commit_id": "sha-of-head-commit",
  "body": "Overall review summary (markdown)",
  "event": "COMMENT",
  "comments": [
    {
      "path": "src/main.py",
      "line": 42,
      "side": "RIGHT",
      "body": "This variable is unused."
    }
  ]
}
```

**Review states (`event`):**
- `COMMENT` — feedback without approval/blocking
- `APPROVE` — approves the PR
- `REQUEST_CHANGES` — blocks merge until resolved
- Omit `event` — creates a `PENDING` review (draft, invisible until submitted)

### Line-Level Comments

**Single-line:**
```json
{ "path": "file.py", "line": 42, "side": "RIGHT", "body": "..." }
```

**Multi-line (range):**
```json
{ "path": "file.py", "start_line": 10, "start_side": "RIGHT", "line": 15, "side": "RIGHT", "body": "..." }
```

**Side:** `RIGHT` for additions/context (default), `LEFT` for deletions (base branch version).

### Suggestion Comments

Use the suggestion fence in comment body:

````markdown
```suggestion
def improved_function():
    return optimized_result
```
````

The suggestion replaces the line(s) the comment is attached to. PR authors can apply with one click ("Commit suggestion") or batch multiple suggestions into one commit.

### Check Runs API (GitHub Apps Only)

`POST /repos/{owner}/{repo}/check-runs`

```json
{
  "name": "AI Code Review",
  "head_sha": "commit-sha",
  "status": "completed",
  "conclusion": "success",
  "output": {
    "title": "Code Review Results",
    "summary": "Found 3 issues in 12 files",
    "annotations": [
      {
        "path": "src/main.py",
        "start_line": 10,
        "end_line": 12,
        "annotation_level": "warning",
        "message": "Potential null reference"
      }
    ]
  }
}
```

**Annotation levels:** `notice`, `warning`, `failure`
**Conclusions:** `success`, `failure`, `neutral`, `cancelled`, `skipped`, `timed_out`, `action_required`
**Limit:** 50 annotations per API call (make multiple calls for more)

### Checks vs Commit Statuses

| Feature | Commit Statuses | Check Runs |
|---|---|---|
| Creator | Any authenticated user/app | GitHub Apps only |
| States | pending/success/failure/error | queued/in_progress/completed + conclusion |
| Line annotations | No | Yes (in PR diff) |
| Rich output | No (description + URL only) | Yes (markdown, images) |
| Re-run | No | Yes (via API) |
| Branch protection | Integrates | Integrates |

Check Runs are strictly superior for code review — line-level annotations appear inline in the PR diff, and rich output allows detailed summary reports.

### Review Lifecycle Endpoints

| Operation | Method | Endpoint |
|---|---|---|
| List reviews | GET | `.../pulls/{pr}/reviews` |
| Create review | POST | `.../pulls/{pr}/reviews` |
| Update review body | PUT | `.../pulls/{pr}/reviews/{id}` |
| Delete pending review | DELETE | `.../pulls/{pr}/reviews/{id}` |
| Submit pending review | POST | `.../pulls/{pr}/reviews/{id}/events` |
| Dismiss review | PUT | `.../pulls/{pr}/reviews/{id}/dismissals` |
| List review comments | GET | `.../pulls/{pr}/reviews/{id}/comments` |

### Comment Reactions

`POST /repos/{owner}/{repo}/pulls/comments/{comment_id}/reactions`

Available: `+1`, `-1`, `laugh`, `confused`, `heart`, `hooray`, `rocket`, `eyes`

Useful for acknowledging command receipt (e.g., reacting with `eyes` when processing a user's review request).

---

## 3. Authentication Models

### Token Comparison

| Token Type | Rate Limit | Expiration | Checks Write | Scalability |
|---|---|---|---|---|
| App installation token | 5,000-12,500/hr | 1 hour | Yes | Scales with org |
| Classic PAT | 5,000/hr | Never (unless unused 1yr) | No | Fixed |
| Fine-grained PAT | 5,000/hr | Mandatory expiry | No | Fixed |
| GITHUB_TOKEN (Actions) | 1,000/hr | Job completion | No | Per-repo |
| OAuth App token | 5,000/hr | Until revoked | No | Fixed |

### GitHub App Token Flow (Recommended)

1. Register GitHub App with required permissions
2. Generate and securely store private key (PEM)
3. Per-request: build JWT (`iss` = app client ID, `iat` = now - 60s, `exp` = now + 600s), sign with RS256
4. Exchange: `POST /app/installations/{installation_id}/access_tokens` with `Authorization: Bearer <JWT>`
5. Use installation token for all API calls (1-hour validity)
6. Refresh proactively before expiry

**Scoping:** Installation tokens can be narrowed to specific repos (max 500) and permissions at creation time.

### OAuth Apps vs GitHub Apps

GitHub officially recommends Apps over OAuth. Apps have fine-grained permissions, bot identity, scaled rate limits, and exclusive Checks API access. OAuth Apps are legacy — they grant broad scopes and act as the authorizing user.

---

## 4. Rate Limits

### Primary Rate Limits

| Authentication | REST (req/hr) | GraphQL (points/hr) | Search (req/min) |
|---|---|---|---|
| Unauthenticated | 60 | N/A | 10 |
| PAT / OAuth | 5,000 | 5,000 | 30 |
| App installation | 5,000-12,500 | 5,000-12,500 | 30 |
| GITHUB_TOKEN | 1,000 | 1,000 | 30 |
| Enterprise Cloud | 15,000 | 15,000 | 30 |

### Secondary Rate Limits (Critical for Code Review)

These are the binding constraints for a tool that creates content:

| Limit | Value |
|---|---|
| Concurrent requests | 100 max |
| Content creation | **80 req/min, 500 req/hr** |
| REST per-endpoint per-min | 900 points (GET=1pt, POST/PATCH/PUT/DELETE=5pt) |
| GraphQL per-min | 2,000 points (query=1pt, mutation=5pt) |

**The content creation limit of 80/min and 500/hr is the most important constraint for a code review tool.** Each review comment, review submission, and check annotation counts.

### Rate Limit Response Headers

Every response includes: `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-used`, `x-ratelimit-reset`, `x-ratelimit-resource`.

### Strategies for Kenjutsu

1. **Batch comments into reviews.** Post a single review with `comments[]` array instead of individual comments. One API call → many annotations.
2. **Use Check Run annotations.** 50 annotations per API call — far more efficient for high-volume findings.
3. **Pending review pattern.** Create review (PENDING) → accumulate all comments → submit once. Atomic operation, single notification to PR author.
4. **Monitor headers proactively.** Throttle when `x-ratelimit-remaining` approaches zero.
5. **Respect `retry-after`.** On 403/429 responses, wait the indicated duration.
6. **Cache aggressively.** Cache file contents, PR metadata, and diff data. Don't re-fetch on every tool invocation.
7. **Debounce on PR updates.** When `synchronize` events arrive (new commits pushed), wait 30-60 seconds before starting review in case more commits follow.

---

## 5. Handling PR Updates

When new commits are pushed to a PR during or after review:

1. **Listen to `synchronize` action** on `pull_request` events.
2. **Track `commit_id` in reviews.** Reviews on outdated commits appear as "outdated" in the UI — this is expected behavior.
3. **Debounce.** Wait 30-60 seconds after `synchronize` before starting a new review (more commits may follow).
4. **Incremental review strategy.** Diff new commits against the previously reviewed commit (`GET /repos/{owner}/{repo}/compare/{base}...{head}`) rather than re-reviewing the entire PR.
5. **Dismiss or update stale reviews** if the PR has fundamentally changed. Use `PUT .../reviews/{id}/dismissals`.
6. **Individual comments cannot be moved** to new line positions after code changes — they must be re-created on the new commit.

---

## 6. Webhook Security

1. **Always verify signatures.** Compute HMAC-SHA256 of the raw payload body using your webhook secret.
2. **Constant-time comparison.** Use `hmac.compare_digest()` (Python), `crypto.timingSafeEqual` (Node.js) — never `==`.
3. **Validate the `X-Hub-Signature-256` header** format before comparing.
4. **Store webhook secret securely** (environment variable or secrets manager, never in code).
5. **Verify UTF-8 encoding** of payload before signature verification.

---

## 7. Permissions Required for Code Review

Minimum permissions for a GitHub App code review tool:

| Permission | Level | Purpose |
|---|---|---|
| `pull_requests` | write | Create reviews, post comments, read PR data |
| `checks` | write | Create check runs with annotations |
| `contents` | read | Read file contents for context beyond diff |
| `metadata` | read | Access repo metadata (always required) |
| `issues` | write | (Optional) Create/update issues from review findings |
| `statuses` | write | (Optional) Post commit statuses if not using checks |

**Subscribe to events:** `pull_request`, `issue_comment`, `pull_request_review_comment`, `push` (optional, for branch protection integration).

---

## 8. Recommendations for Kenjutsu

1. **Build a GitHub App as primary integration.** This is non-negotiable for a production tool. The rate limits, Checks API, bot identity, and marketplace distribution are all critical.

2. **Offer a GitHub Action as secondary option.** Lower barrier to entry, zero infrastructure for users. Use for OSS adoption and self-hosted scenarios.

3. **Use the pending review pattern** for all feedback submission. Create review → accumulate comments → submit atomically. One notification to the PR author, not N.

4. **Combine PR reviews with Check Runs.** Use Check Runs for summary status (pass/fail with annotation count) and PR reviews for detailed inline feedback. This gives users both the status check integration and the conversational review experience.

5. **Design for the content creation rate limit.** 80 req/min, 500 req/hr is the binding constraint. Batch aggressively. For very large PRs, prioritize findings rather than exhaustively commenting.

6. **Implement webhook signature verification from day one.** This is a security requirement, not a nice-to-have. The PR-Agent CVEs demonstrate the consequences of skipping input validation.

7. **Plan for incremental review.** Track reviewed commit SHAs. On new pushes, review only the delta. This saves LLM costs and produces more useful feedback.

---

## Sources

- [GitHub Docs — GitHub Apps](https://docs.github.com/en/apps)
- [GitHub Docs — Pull Request Reviews API](https://docs.github.com/en/rest/pulls/reviews)
- [GitHub Docs — Check Runs API](https://docs.github.com/en/rest/checks/runs)
- [GitHub Docs — Rate Limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [GitHub Docs — Webhook Security](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
- [CodeRabbit GitHub App permissions](https://github.com/apps/coderabbitai)
- [PR-Agent GitHub Action workflow](https://github.com/qodo-ai/pr-agent)
