# PR-Agent Deep-Dive: Architecture, Integration, and Fork Evaluation

- **Status:** review
- **Author:** Chief Architect
- **Date:** 2026-03-23
- **Issue:** DEM-106
- **Parent:** DEM-104

---

## Executive Summary

PR-Agent (by Qodo, formerly CodiumAI) is the most relevant open-source reference implementation for AI-powered code review. This deep-dive analyzes its architecture end-to-end. The most significant finding is a **license change from Apache 2.0 to AGPL-3.0** in May 2025, which fundamentally constrains fork-and-extend strategies for commercial products. The recommendation is a hybrid approach: study PR-Agent's architecture and prompt engineering, then build clean.

---

## 1. Architecture Overview

### Repository Structure

The codebase lives at `github.com/qodo-ai/pr-agent`. Pure Python package (~25,600 LOC across 113 files, 41 test files).

```text
pr_agent/
  agent/           Command dispatcher (PRAgent class, command2class map)
  algo/            Core algorithms: diff processing, token handling, LLM calls
    ai_handlers/   LLM provider abstraction (base, litellm, openai, langchain)
    __init__.py    MAX_TOKENS dict (~200 model definitions)
  git_providers/   Platform abstraction: GitHub, GitLab, Bitbucket, Azure DevOps,
                   Gerrit, Gitea, CodeCommit, local
  servers/         Entry points: github_app (FastAPI), github_action_runner,
                   gitlab_webhook, bitbucket_app, gerrit_server, gitea_app
  tools/           Tool classes: PRReviewer, PRDescription, PRCodeSuggestions,
                   PRQuestions, PRUpdateChangelog, PRAddDocs, etc.
  settings/        TOML configs: configuration.toml, prompt templates, ignore patterns
```

### Key Architectural Decisions

1. **Command dispatcher pattern.** A hardcoded `command2class` dict maps slash commands to tool classes. No plugin system, no dynamic loading. Adding tools requires code changes.

2. **Global state via Dynaconf.** Configuration uses `get_settings()` (200+ call sites). Request-scoped via `starlette_context` to prevent concurrency issues, but creates heavy coupling throughout the codebase.

3. **One LLM call per tool.** Each tool (`/review`, `/describe`, `/improve`) makes a single LLM call for standard-size PRs. Fast (~30s), but fundamentally limits review depth to what fits in one context window.

4. **Provider abstraction.** `GitProvider` ABC defines the interface for git platform interactions. Implementations exist for 9 platforms, but interface consistency is poor (inconsistent return types, argument signatures across providers — documented in issue #2259).

---

## 2. PR Processing Lifecycle

### Full Flow: Trigger to Comment

```text
Webhook/Action → Event Ingestion → Repo Config Merge → Command Routing
→ Tool Init → Diff Generation → Token Budget Check → Prompt Rendering
→ LLM Call (with fallback) → YAML Parsing → Markdown Conversion → Publish
```

**Step 1 — Event ingestion.** In GitHub App mode, a FastAPI server receives POST webhooks. HMAC-SHA256 signature verification. Deep-copies global settings into request-scoped context. Dispatches to `handle_request()` as background task. In Action mode, reads `GITHUB_EVENT_PATH` payload directly.

**Step 2 — Config merge.** `apply_repo_settings(pr_url)` fetches `.pr_agent.toml` from the repo's default branch and merges it into the running config. Also checks `pyproject.toml` for `[tool.pr-agent]` section.

**Step 3 — Command routing.** Parses command string via `shlex`. Validates arguments. Looks up tool class in `command2class` dict. Instantiates.

**Step 4 — Tool initialization.** Each tool's `__init__` initializes the git provider, detects main PR language, fetches PR metadata (title, branch, description, commit messages), builds a Jinja2 variable dict, creates a `TokenHandler` that renders prompt templates (minus diff) to calculate baseline token usage.

**Step 5 — Diff generation.** `get_pr_diff()` calls `git_provider.get_diff_files()` to get `FilePatchInfo` objects. Sorts by main language. Extends each patch with configurable context lines. Checks token budget. If over limit, enters compressed mode (details in Section 3).

**Step 6 — LLM call.** `retry_with_fallback_models()` renders the full prompt with diff, calls the AI handler. On failure, tries each model in `fallback_models` sequentially. Default fallback: `o4-mini`.

**Step 7 — Response parsing.** Extracts YAML from LLM response via `load_yaml()` with extensive repair logic for common YAML errors. Converts parsed data to Markdown.

**Step 8 — Publishing.** Posts results back to the git platform. Uses `publish_persistent_comment()` (edit-or-create pattern) for `/review` and `/improve`. Uses `publish_inline_comments()` for line-specific review comments via GitHub's review API.

---

## 3. Diff Handling and Chunking

### Patch Format

PR-Agent uses a custom "decoupled hunk" format, not standard unified diff. The function `decouple_and_convert_to_hunks_with_lines_numbers()` transforms standard `@@` hunks into separate new/old views:

```diff
## File: 'src/file.py'
@@ -881,10 +881,12 @@
__new hunk__
881        line1
882        line2
887 +      new_line
888 +      new_line2
__old hunk__
        line1
        line2
-       removed_line
```

Line numbers appear only on the new side. This format helps the LLM reason about change positioning for inline suggestions.

### Token Budget Management

- `TokenHandler` uses tiktoken (`o200k_base` for non-OpenAI, model-specific for OpenAI). Anthropic models use the Anthropic token counting API.
- `OUTPUT_BUFFER_TOKENS_SOFT_THRESHOLD = 1500` — reserved for LLM output.
- `max_model_tokens` default: 32,000 — caps all models regardless of actual capacity.
- `MAX_TOKENS` dict maps ~200 model IDs to context limits (4K to 1M+).

**Critical observation:** The 32K default cap means most deployments use a fraction of available context. Users who don't override this miss the benefit of larger context windows.

### Large Diff Strategies

| Strategy | When Used | Mechanism |
|---|---|---|
| **Clip** (`large_patch_policy = "clip"`) | Default | Truncates individual large patches to fit remaining token budget. Character-level truncation with `delete_last_line=True` to avoid mid-line cuts. |
| **Skip** (`large_patch_policy = "skip"`) | Alternative | Omits files that don't fit entirely. |
| **Multi-patch** (`get_pr_multi_diffs()`) | `/improve` extended mode | Splits diff into multiple chunks. Each chunk gets a separate LLM call (up to `max_number_of_calls = 3`). Calls can run in parallel. |
| **Large PR handling** | `/describe` with `enable_large_pr_handling` | Multiple patch groups, each with its own LLM call (up to `max_ai_calls = 4`). One call reserved for summarization. |
| **Deletion omission** | Always | Deletion-only hunks stripped to save tokens. Deleted files listed by name only. |
| **Dynamic context** | `allow_dynamic_context=true` (default) | Extends hunks up to 10 extra lines to include enclosing function/class definitions. |

### Unprocessed File Tracking

Files that don't fit the token budget are appended as a text list: "Additional modified files (insufficient token budget to process)." The LLM sees their names but not their content.

---

## 4. GitHub Integration

### Three Deployment Modes

| Mode | Auth | Entry Point | Use Case |
|---|---|---|---|
| **GitHub App** | App private key + app_id → per-installation tokens | FastAPI webhook server | Production SaaS / self-hosted |
| **GitHub Action** | Built-in `GITHUB_TOKEN` | `github_action_runner.py` in Docker | CI/CD pipeline integration |
| **Polling** | Personal access token | `github_polling.py` | Development / limited environments |

### GitHub API Usage (via PyGithub)

- **Diff files:** `pr.get_files()` (compare API). Full file content fetched for files under `MAX_FILES_ALLOWED_FULL = 50`.
- **PR comments:** `pr.create_issue_comment()` for top-level PR comments.
- **Review comments:** `pr.create_review(commit, comments)` for inline review comments. Falls back to individual comments if review creation fails (e.g., invalid line references).
- **Labels:** `pr.set_labels()` for review effort/security labels.
- **Reactions:** `comment.create_reaction("eyes")` to acknowledge command receipt.
- **Persistent comments:** Searches for header marker in existing comments, edits if found.
- **Rate limits:** `RateLimitExceededException` handling with `ratelimit_retries = 5`.
- **Comment size:** Capped at `max_comment_chars = 65000` (GitHub's limit).

### Webhook Signature Verification

HMAC-SHA256 via `x-hub-signature-256` header. Optional but recommended. Verification happens before any processing.

---

## 5. Multi-LLM Provider Support

### Architecture

Two-layer abstraction:

1. **`BaseAiHandler`** — abstract base class defining `chat_completion(model, system, user, temperature, img_path)`.
2. **`LiteLLMAIHandler`** — primary implementation wrapping LiteLLM's `acompletion()`. LiteLLM provides a unified OpenAI-compatible interface to 100+ providers.

### Supported Providers

OpenAI (direct, Azure, Azure AD), Anthropic (direct, Bedrock, Vertex AI), Google (Vertex AI, AI Studio/Gemini), Cohere, Replicate, Groq, xAI/Grok, HuggingFace (Inference API + custom endpoints), Ollama (local), DeepSeek, DeepInfra, Mistral/Codestral, OpenRouter, WatsonX.

### Model-Specific Handling

| Model Class | Special Behavior |
|---|---|
| DeepSeek Reasoner, o1 series | System prompt concatenated into user message (no system role) |
| o-series, GPT-5 codex variants | Temperature parameter omitted |
| o3, o4-mini | `reasoning_effort` parameter (low/medium/high) |
| Claude 3.7 Sonnet | Extended `thinking` parameter with configurable budget tokens |
| `openai/qwq-plus` | Requires streaming mode |

### Fallback Chain

Primary model + `fallback_models` list (default: `["o4-mini"]`). Sequential fallback on failure. LiteLLM handler retries 2 times for API errors, excluding rate limit errors.

---

## 6. Tool Architecture

### /review (PRReviewer)

- **Prompt:** `pr_reviewer_prompts.toml`. Pydantic schema defines expected YAML output structure.
- **Output:** Ticket compliance check, effort estimate (1-5), relevant tests (yes/no), `key_issues_to_review` (file/line/issue tuples, max 3), security concerns.
- **Flow:** Single LLM call with full diff. YAML parsed, converted to Markdown with collapsible sections.
- **Labels:** Auto-sets "Review effort N/5" and "Possible security concern" on the PR.
- **Incremental:** `-i` flag reviews only new commits since last review.

### /describe (PRDescription)

- **Prompt:** `pr_description_prompts.toml`. Generates type, description, title, per-file summaries.
- **Flow:** Uses `ModelType.WEAK` (cheaper model). Large PRs split into multiple patches with up to 4 parallel LLM calls.
- **Publishes:** Directly edits the PR title and description body.

### /improve (PRCodeSuggestions)

- **Two-phase approach:**
  1. Generate suggestions (up to 3 per chunk).
  2. Self-reflect: a second LLM call scores each suggestion (0-10), validates line numbers, filters low-quality ones.
- **Extended mode:** Splits diff into chunks, parallel LLM calls (up to 3).
- **Thresholds:** Score >= 9 = strong suggestion, >= 7 = medium.
- **Committable:** When enabled, posts suggestions with GitHub's "Apply suggestion" button.

### /ask (PRQuestions)

- Free-form Q&A about the PR. Uses `ModelType.WEAK`. Supports image inputs (multimodal). Optional conversation history.

---

## 7. Configuration System

Priority order (lowest to highest):

1. **Hardcoded defaults** — `configuration.toml` (377 lines, committed to repo)
2. **Prompt templates** — separate TOML files under `settings/`
3. **Local `pyproject.toml`** — `[tool.pr-agent]` section
4. **Repository `.pr_agent.toml`** — fetched from repo's default branch at runtime
5. **Environment variables** — loaded by Dynaconf (no prefix required)
6. **CLI arguments** — inline with commands (e.g., `/review --pr_reviewer.num_max_findings=5`)
7. **Cloud secrets** — AWS Secrets Manager or GCS (fills empty values only)

Key config sections: `[config]`, `[pr_reviewer]`, `[pr_description]`, `[pr_code_suggestions]`, `[pr_questions]`, `[github]`, `[github_app]`, `[gitlab]`, `[bitbucket_app]`, `[litellm]`, `[best_practices]`.

File filtering via `ignore.toml` (glob and regex patterns) and `generated_code_ignore.toml` (framework-specific generated code exclusions).

---

## 8. Known Weaknesses and Limitations

### Security Vulnerabilities (CVE-2024-51355, CVE-2024-51356)

Documented by Kudelski Security:

- **Prompt injection:** `/ask` inserts user text into LLM prompts without sanitization.
- **Configuration override abuse:** CLI args like `--openai.key=attacker_url` can redirect API calls and exfiltrate secrets.
- **GitLab privilege escalation:** Injected GitLab quick actions (`/approve`, `/merge`) execute with PR-Agent's elevated permissions.

### Architectural Weaknesses

1. **No plugin system.** All commands hardcoded in `command2class` dict. Custom tools require forking.
2. **Conservative token defaults.** `max_model_tokens = 32000` caps models with 1M+ context windows. Most users don't know to raise it.
3. **Single-pass diff analysis.** One LLM call per tool. No codebase context beyond the diff. Misses cross-file interactions, architectural patterns, and code outside the changed hunks.
4. **YAML output fragility.** LLM responses expected in strict YAML. Extensive repair logic, but malformed output still causes failures.
5. **Stateless.** No memory between runs. Incremental review (`-i`) only filters commits — doesn't carry forward context.
6. **Provider inconsistencies.** Return types and argument signatures vary across GitProvider implementations (issue #2259).
7. **God files.** `algo/utils.py` is 1,507 lines — a dumping ground spanning markdown conversion, token handling, YAML parsing, model selection.
8. **Heavy global state.** 200+ `get_settings()` calls create hidden coupling. Refactoring is a major effort.
9. **Mandatory dependency bloat.** All 35 dependencies install regardless of which providers you use (boto3, azure-devops, google-cloud-aiplatform, etc.). No optional/extras mechanism.
10. **No monorepo awareness.** All changed files treated as one flat list regardless of project boundaries.

### Feature Gaps (OSS vs Qodo Merge Paid)

Auto-best-practices learning, static analysis integration, SOC2 compliance, custom model hosting, advanced Jira/ticket integration, and multi-agent expert review (Qodo 2.0) are all paid-only. The README now states "This repo is not the Qodo free tier!"

---

## 9. Fork vs Build Evaluation

### License — The Critical Finding

**PR-Agent changed from Apache 2.0 to AGPL-3.0 in May 2025** (PR #1809, v0.30). The maintainer's stated reason: companies were taking the open-source, packaging it as-is, and selling it without credit.

**AGPL-3.0 implications for a commercial product:**

- **Section 13 (Remote Network Interaction):** If you modify the program and users interact with it over a network, you MUST offer your complete modified source code to those users.
- **SaaS deployment of a fork = mandatory source disclosure.** Running a modified PR-Agent as a service requires making all source code available.
- **No closed-source commercial product** is possible on an AGPL fork.
- **v0.29 (May 17, 2025) was the last Apache 2.0 release.** Forking from that tag allows proprietary use (with attribution), but freezes upstream improvements at May 2025.

**This updates the competitive analysis (DEM-105), which lists PR-Agent as "Apache 2.0."** That was correct at time of initial research but is now outdated.

### Decision Matrix

| Factor | Fork (AGPL) | Fork v0.29 (Apache 2.0) | Build from Scratch | Hybrid (Study + Build) |
|---|---|---|---|---|
| **Time to MVP** | 2-4 weeks | 4-6 weeks | 10-14 weeks | 10-14 weeks |
| **Commercial SaaS** | No (must open-source) | Yes | Yes | Yes |
| **Architecture quality** | Poor (inherited debt) | Poor (inherited debt) | Excellent | Excellent |
| **Upstream improvements** | Available (must stay AGPL) | Frozen at May 2025 | N/A | N/A |
| **Legal risk** | High (AGPL viral clause) | Low | None | Very low |
| **Maintainability** | Low | Low-Medium | High | High |

### Recommendation: Hybrid Approach

**Study PR-Agent's architecture, then build clean.** This is the recommended path for a commercial product.

**What to study and borrow (legally safe):**

1. **Prompt engineering strategies.** The TOML prompt files are the most valuable artifact. Techniques are not copyrightable: structured output approach (Pydantic models in prompts, YAML output format), hunk/old-hunk formatting, self-reflection scoring. These can be independently reimplemented.

2. **Diff processing algorithms.** Token-aware chunking, dynamic context expansion, patch extension are algorithmic ideas. Key source files to study: `algo/git_patch_processing.py` (hunk extension), `algo/pr_processing.py` (token-budget-aware ordering), `algo/token_handler.py`.

3. **Configuration schema.** The `configuration.toml` is a comprehensive reference for what knobs users need. Use as a feature checklist.

4. **Provider interface design.** Study `GitProvider` ABC methods to understand what operations a code review tool needs, then design a cleaner version with consistent interfaces.

**What to avoid:**

- Do not copy-paste any code from post-May-2025 commits (AGPL).
- Prefer clean-room reimplementation even for pre-May-2025 code to avoid copyright claims.
- Do not fork and "just change things" — the global state architecture will resist modification at every turn.

### Alternative: Fork from v0.29 (Apache 2.0)

If speed-to-market is critical, forking from the last Apache 2.0 tag is viable but carries significant technical debt. Plan for a major refactoring investment within the first quarter. You lose ~10 months of improvements (prompt refinements, new model support, bug fixes).

---

## 10. Key Takeaways for Kenjutsu

1. **AGPL kills the fork path for a commercial product.** The hybrid approach (study + build) is the only viable long-term strategy unless we want to open-source Kenjutsu itself.

2. **The diff processing pipeline is the most reusable intellectual property.** Token-aware chunking, dynamic context expansion, and the decoupled hunk format are well-designed solutions to real problems we'll face.

3. **The prompt engineering is battle-tested.** Months of iteration on review/describe/improve prompts with Pydantic-schema-driven structured output. Worth studying thoroughly before writing our own.

4. **PR-Agent's weaknesses are our design requirements.** No codebase context beyond diff, no plugin system, no monorepo awareness, single-pass analysis, YAML fragility — each weakness becomes an explicit requirement for Kenjutsu's architecture.

5. **The provider abstraction concept is right, the implementation is wrong.** We need a git platform abstraction layer, but it should be designed with consistent interfaces and proper dependency injection from the start.

6. **Token budget management is a solved problem.** PR-Agent's approach works. We can adopt the same strategy (model-aware limits, soft/hard thresholds, greedy patch filling) without copying code.

---

## Sources

- [qodo-ai/pr-agent GitHub Repository](https://github.com/qodo-ai/pr-agent)
- [Qodo Merge Documentation](https://qodo-merge-docs.qodo.ai/)
- [Kudelski Security — Multiple Vulnerabilities in PR-Agent](https://kudelskisecurity.com/research/careful-where-you-code-multiple-vulnerabilities-in-ai-powered-pr-agent)
- [PR-Agent Open Issues](https://github.com/qodo-ai/pr-agent/issues)
- Source code analysis of PR-Agent repository (direct inspection)
