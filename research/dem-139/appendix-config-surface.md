# Appendix: Configuration Surface Map — PR-Agent Prompt Behavior

- **Status:** review
- **Author:** Research Specialist
- **Date:** 2026-03-27
- **Issue:** DEM-158
- **Parent:** DEM-139

---

This appendix maps every PR-Agent configuration setting that affects prompt behavior — what the model sees, how it's instructed, and what output it produces. Operational settings (webhook URLs, authentication, etc.) are excluded.

## Global Settings (`[config]`)

These affect all tools.

| Setting | Type | Default | Effect on Prompt |
|---------|------|---------|-----------------|
| `model` | string | varies | Which LLM receives the assembled prompt |
| `fallback_models` | list | `["o4-mini"]` | Fallback model chain on primary failure |
| `model_reasoning` | string | — | Dedicated model for scoring/reflect phases |
| `max_model_tokens` | int | model-dependent | Hard cap on context window; controls diff truncation |
| `model_token_count_estimate_factor` | float | 0.3 | Safety margin on token estimates; higher = more conservative truncation |
| `response_language` | string | `"en"` | Instructs model to respond in specified locale |
| `temperature` | float | 0.2 | Sampling temperature; lower = more deterministic |
| `seed` | int | — | Reproducibility seed for supported models |
| `reasoning_effort` | string | — | `"low"/"medium"/"high"` for reasoning-capable models |
| `duplicate_prompt_examples` | bool | false | Repeats YAML example at end of user prompt for weaker models |
| `custom_reasoning_model` | bool | false | Disables system messages and temperature for non-chat models |

## Diff Processing Settings (`[config]`)

These control what diff content reaches the prompt.

| Setting | Type | Default | Effect on Prompt |
|---------|------|---------|-----------------|
| `patch_extra_lines_before` | int | 3 | Context lines before each hunk |
| `patch_extra_lines_after` | int | 1 | Context lines after each hunk |
| `allow_dynamic_context` | bool | true | Extends hunks with enclosing function/class context |
| `max_extra_lines_before_dynamic_context` | int | varies | Ceiling on dynamic context expansion |
| `large_patch_policy` | string | `"clip"` | Per-file overflow: `"clip"` (truncate) or `"skip"` (drop) |
| `patch_extension_skip_types` | list | `[".md", ".txt"]` | Extensions whose patches get no extra context lines |
| `max_description_tokens` | int | varies | Token budget for PR description injected into prompt |
| `max_commits_tokens` | int | varies | Token budget for commit messages injected into prompt |
| `skip_keys` | list | `[]` | Fields suppressed from prompt variable injection |

## File Exclusion Settings

Layered filtering system — each layer handles different exclusion patterns.

| Layer | Setting | Location | Scope |
|-------|---------|----------|-------|
| Built-in | `bad_extensions` | `language_extensions.toml` | Binary, media, compiled files |
| Built-in | `is_valid_file()` hard-coded list | `language_handler.py` | `package-lock.json`, `yarn.lock`, `composer.lock`, `Gemfile.lock`, `poetry.lock` |
| Config | `use_extra_bad_extensions` | `[config]` | Extends blocklist with `.md`, `.txt` |
| Config | `ignore_language_framework` | `[config]` | Framework-level codegen exclusion (protobuf, OpenAPI, GraphQL, gRPC) |
| Per-repo | `ignore.glob` | `ignore.toml` / `.pr_agent.toml` | Glob patterns for file exclusion |
| Per-repo | `ignore.regex` | `ignore.toml` / `.pr_agent.toml` | Regex patterns for file exclusion |

## PR-Level Bypass Settings (`[config]`)

Prevent tools from running on matching PRs — no prompt assembled at all.

| Setting | Type | Effect |
|---------|------|--------|
| `ignore_pr_title` | regex list | Skip PRs matching title patterns |
| `ignore_pr_labels` | list | Skip PRs with matching labels |
| `ignore_pr_source_branches` | regex list | Skip PRs from matching source branches |
| `ignore_pr_target_branches` | regex list | Skip PRs targeting matching branches |
| `ignore_pr_authors` | list | Skip PRs by matching authors |
| `ignore_repositories` | list | Skip entire repositories |
| `ignore_bot_pr` | bool | Skip bot-authored PRs |
| `push_trigger_ignore_merge_commits` | bool | Skip merge commit push triggers |

## Per-Tool: /review (`[pr_reviewer]`)

| Setting | Type | Default | Effect on Prompt |
|---------|------|---------|-----------------|
| `extra_instructions` | string | `""` | Free-text appended to system prompt |
| `num_max_findings` | int | 3 | Maximum `key_issues_to_review` items in schema |
| `require_estimate_effort_to_review` | bool | true | Toggles effort estimate field in schema |
| `require_security_review` | bool | true | Toggles security concerns field in schema |
| `require_tests_review` | bool | true | Toggles test coverage analysis in schema |
| `require_can_be_split_review` | bool | false | Toggles PR-splitting analysis (`SubPR` model) |
| `require_todo_scan` | bool | false | Toggles TODO comment scanner in schema |
| `require_ticket_analysis_review` | bool | true | Toggles `TicketCompliance` model in schema |
| `require_estimate_contribution_time_cost` | bool | false | Toggles `ContributionTimeCostEstimate` in schema |
| `require_score_review` | bool | false | Toggles overall review score field |

## Per-Tool: /describe (`[pr_description]`)

| Setting | Type | Default | Effect on Prompt |
|---------|------|---------|-----------------|
| `extra_instructions` | string | `""` | Free-text appended to system prompt |
| `enable_pr_diagram` | bool | true | Toggles Mermaid flowchart field in schema |
| `enable_semantic_files_types` | bool | true | Toggles `pr_files` (file walkthrough) in schema |
| `include_file_summary_changes` | bool | conditional | Toggles `changes_summary` in `FileDescription` |
| `use_bullet_points` | bool | true | Bullet format for description field |
| `collapsible_file_list` | string | `"adaptive"` | Collapsible rendering in output |
| `enable_large_pr_handling` | bool | false | Multi-chunk processing mode |
| `max_ai_calls` | int | varies | Maximum generation calls for large PRs |
| `use_description_markers` | bool | false | Placeholder-based description updates |
| `inline_file_summary` | bool | false | Alternative file summary rendering |
| `enable_custom_labels` | bool | false | User-defined PR type labels |

## Per-Tool: /improve (`[pr_code_suggestions]`)

| Setting | Type | Default | Effect on Prompt |
|---------|------|---------|-----------------|
| `extra_instructions` | string | `""` | Free-text appended to system prompt |
| `num_code_suggestions_per_chunk` | int | 3 | Suggestions requested per diff chunk |
| `max_number_of_calls` | int | 3 | Maximum diff chunks processed |
| `suggestions_score_threshold` | int | 0 | Minimum score to keep a suggestion |
| `new_score_mechanism_th_high` | int | 9 | Score threshold for "High" impact tier |
| `new_score_mechanism_th_medium` | int | 7 | Score threshold for "Medium" impact tier |
| `focus_only_on_problems` | bool | false | Narrow to critical bugs only; restricted label taxonomy |
| `commitable_code_suggestions` | bool | false | Inline committable suggestions vs. table format |
| `dual_publishing_score_threshold` | int | 0 | Above threshold: publish both table and inline |
| `demand_code_suggestions_self_review` | bool | false | Adds author self-review checkbox |
| `decouple_hunks` | bool | true | Uses `__new hunk__` / `__old hunk__` split diff format |

## Per-Tool: /ask (`[pr_questions]`)

| Setting | Type | Default | Effect on Prompt |
|---------|------|---------|-----------------|
| `use_conversation_history` | bool | true | Threads prior Q&A into prompt (line-level variant) |
| `enable_help_text` | bool | false | Appends help text to responses |

## User-Configured Settings (Most Changed)

Based on commit history analysis, these are the settings users most frequently override:

1. **`extra_instructions`** — Free-text prompt appendix (all tools). The primary customization surface.
2. **`ignore.glob` / `ignore.regex`** — Per-repo file exclusions.
3. **`ignore_language_framework`** — Generated code exclusion by framework.
4. **`response_language`** — Localized responses.
5. **`num_code_suggestions_per_chunk` / `num_max_findings`** — Volume controls.
6. **`suggestions_score_threshold`** — Quality filter aggressiveness.
7. **`max_model_tokens`** — Cost control (lower = cheaper).
8. **`pr_commands`** (per provider) — Which tools auto-run on PR open.

## Implications for Kenjutsu

1. **Expose `extra_instructions` as the primary user customization.** Don't require template editing.
2. **Implement layered file exclusions** from built-in to per-repo to per-run.
3. **Per-field token budgets** prevent any single context source from crowding out the diff.
4. **Feature-flag all optional schema sections.** Every output group (security, tests, ticket compliance) should be toggleable.
5. **Config scoping: org defaults → repo overrides → per-run overrides.** PR-Agent uses `use_wiki_settings_file` → `use_repo_settings_file` → `use_global_settings_file` precedence.
6. **Ship sane defaults, override only what you need.** Don't expose the full config surface to users — just the frequently-changed settings listed above.
