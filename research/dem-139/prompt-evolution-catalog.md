# Prompt Evolution Catalog — PR-Agent Study

- **Status:** review
- **Author:** Research Specialist
- **Date:** 2026-03-27
- **Issue:** DEM-158
- **Parent:** DEM-139

---

## Executive Summary

This catalog documents how PR-Agent's prompt engineering evolved across its four core tools (`/review`, `/describe`, `/improve`, `/ask`) over 700+ commits to `pr_agent/settings/*.toml`. The analysis extracts patterns, architectural decisions, and lessons learned — not code — to inform Kenjutsu's Phase 2 prompt design.

Key findings:
- **Structured output schemas (Pydantic-in-prompt) are the most durable pattern**, stable for 2+ years while everything else iterated.
- **Two-phase generate→score is essential for suggestion quality** — the self-reflection pattern filters 30-50% of generated suggestions.
- **Behavioral meta-instructions arrived late but matter most** — telling the model *what to flag* and *how to write comments* took 2 years to appear but address the core quality problem.
- **Quantitative constraints outperform qualitative ones** — "up to 8 words" beats "concise" every time.
- **14 edge case patterns** are handled across diff processing, token management, and file filtering layers.

---

## /review — PRReviewer Prompts

### Current Architecture

The review prompt is a Jinja2-templated TOML with `system` and `user` sections rendered at runtime.

**System prompt structure:**
1. Role declaration ("You are PR-Reviewer...")
2. Diff format documentation (the `__new hunk__` / `__old hunk__` split format with line numbers)
3. Conditional AI metadata note
4. Behavioral sections: "Determining what to flag" and "Constructing comments" (added March 2026)
5. Optional `extra_instructions` injection point
6. Output schema as inline Pydantic class definitions
7. Example output block

**User prompt structure:**
1. Optional ticket context (`--PR Ticket Info--`) with URL, title, labels, body, requirements
2. PR metadata: title, branch, date, description
3. Optional user Q&A context
4. The diff itself

**Output schema fields (all conditional on config flags):**
- `key_issues_to_review`: `List[KeyIssuesComponentLink]` — file path, line range, header, content, referenced variables
- Effort estimate (1-5 integer)
- Security concerns
- Ticket compliance (`TicketCompliance` model)
- Test coverage analysis
- Can-be-split analysis (`SubPR` model)
- TODO scanning (`TodoSection` model)

### Evolution Timeline

| Date | Change | Why | Impact |
|------|--------|-----|--------|
| Pre-2023-11 | YAML schema format; combined "PR Analysis" + "PR Feedback"; code suggestions embedded | Original design | Monolithic output |
| 2024-02-08 | Removed "PR Analysis" narrative section entirely | Stripped verbose output to focus on actionable feedback | Leaner, more focused output |
| 2024-03-01 | Output schema switched from inline YAML to Pydantic class definitions | Schema-as-code for stronger typing | More precise model compliance |
| 2024-06-09 | `possible_issues` → `key_issues_to_review`; effort field changed from `str` to `int` | Precision over prose | Machine-readable effort scores |
| 2024-07-14 | `key_issues_to_review` changed from free-text to `List[KeyIssuesComponentLink]` with file path, line range, header | Machine-readable issue references | Clickable links, code highlighting |
| 2024-10-10 | Added `TicketCompliance` model with requirements tracking | Closes review-to-ticket gap | Issue tracker integration |
| 2024-12-25 | Removed all code suggestion fields from review prompt | Separated concerns | Each tool independently tunable |
| 2025-01-19 | Added explicit diff format documentation and partial-context guidance | Addressed false positives from incomplete context | Fewer hallucinated findings |
| 2026-03-23 | Added "Determining what to flag" and "Constructing comments" behavioral sections | Fighting over-flagging and low-quality findings | Noise reduction |

### Lessons for Kenjutsu

1. **Start with structured output from day one.** PR-Agent spent months with free-text fields before migrating to `List[StructuredObject]`. Define typed finding models (file, line range, severity, category, description) in v1.

2. **Behavioral meta-sections are not optional polish.** "Determining what to flag" and "Constructing comments" address the core quality problem: LLMs over-flag, overstate severity, and get tone wrong. These belong in v1, not as a late addition.

3. **Separate concerns early.** Code suggestions lived in the review prompt for over a year before extraction. Each concern (findings, suggestions, ticket compliance) should be a distinct tool or schema section from the start.

4. **Make every output field feature-flagged.** Operators can turn off noise sources. Kenjutsu should architect finding groups (security, performance, test coverage) as independently toggleable.

5. **The diff format is as important as the prompt.** The `__new hunk__` / `__old hunk__` split format with explicit line numbers prevents confusion about what changed. Invest in diff presentation.

6. **Partial code context requires explicit guard rails.** "Don't treat opening braces as incomplete code" and "don't question imports that may be defined elsewhere" prevent speculation about unseen code.

7. **Plan for ticket/issue integration from the start.** Ticket compliance was added 14 months in and required schema changes. Design the context injection slot early.

8. **Configurable finding count matters.** `num_max_findings` (default: 3) prevents quota-filling with weak findings. Default conservatively.

---

## /describe — PRDescription Prompts

### Current Architecture

Two-part Jinja2 template with `system` and `user` sections.

**System prompt:** Role declaration, behavioral rules, Pydantic schema (`PRDescription`), and canonical YAML output example.

**User prompt:** Related tickets, previous title/description, branch name, commit messages, and the full diff.

**Output schema fields:**
- `type`: one or more `PRType` enum values (Bug fix, Tests, Enhancement, Documentation, Other)
- `description`: 1-4 bullet points, each max 8 words, sub-bullets for large PRs, ordered by importance
- `title`: concise, descriptive
- `changes_diagram`: optional Mermaid LR flowchart (conditional on `enable_pr_diagram`)
- `pr_files`: `List[FileDescription]` with filename, changes_summary, changes_title, label

### Evolution Timeline

| Date | Change | Why | Impact |
|------|--------|-----|--------|
| 2023-10-23 | Replaced hardcoded PR type enum with `{{ custom_labels }}` template variable | Per-repo custom label sets | Extensibility |
| 2023-12-04 | **Major pivot**: replaced label-grouped file lists with per-file `FileDescription` (file → label + summary) | Label grouping confused models; per-file is cleaner | Stable architecture found |
| 2024-01-05 | Added instruction: "return label member value, not enum name" | Models returned Python names instead of display values | Schema precision |
| 2024-01-21 | Added `changes_title` field (5-10 word summary) per file | Improve scannability | Better tables |
| 2024-10-10 | Added related tickets block to user prompt | Ticket-grounded descriptions | Context alignment |
| 2024-12-29 | Removed `language` field; made `changes_summary` conditional; increased file cap 15→20 | Simplification pass | Reduced noise |
| 2024-12-31 | Quantified bullet constraint: "up to four bullet points, each up to 8 words" | Hard numeric limits beat "concise" | Consistent output |
| 2025-01-02 | Added `duplicate_prompt_examples` (repeat example at end of user prompt) | Weaker models need example near generation point | Model compatibility |
| 2025-05-25 | Added Mermaid flowchart diagram field (7 fixup commits in one day) | Visual representation | Required extensive iteration |
| 2025-06-24 | Diagram enabled by default | Stabilized enough | Broader adoption |

### Lessons for Kenjutsu

1. **Use Pydantic-schema-as-prompt from the start.** Define output as Pydantic model definitions in the system prompt. Each field's description is a mini-prompt. Most durable pattern, stable 2+ years.

2. **Quantify output constraints numerically.** "1-4 bullet points, each up to 8 words" is a lesson learned over 6 commits. Design with numeric bounds from the start.

3. **Per-item structure beats grouped structure.** One row per file/finding rather than grouping under category headers. The team tried grouping and abandoned it within days.

4. **Field ordering in the schema is output order.** Put most important fields first — the model generates them in order and leading fields get the most attention.

5. **Repeat examples for weaker models.** The `duplicate_prompt_examples` pattern — repeating a YAML example right before the response block — is a measurable quality lever for smaller models.

6. **Rendering-dependent features need 3-5x more prompt engineering.** The Mermaid diagram went through 7 commits in a single day. Budget accordingly for any structured visualization.

7. **Inject ticket/issue context before the diff.** Placing context at the top grounds the model's interpretation against intended goals, not just what changed.

---

## /improve — PRCodeSuggestions Prompts

### Current Architecture

The `/improve` tool uses a **two-phase pipeline**:

**Phase 1 — Generation:**
- Splits PR diff into chunks (up to `max_number_of_calls=3` chunks, `num_code_suggestions_per_chunk=3` per chunk)
- Diff presented in **decoupled hunk format** (`__new hunk__` / `__old hunk__` split) — the LLM sees before/after states in isolation
- Produces structured YAML: `relevant_file`, `language`, `existing_code`, `suggestion_content`, `improved_code`, `one_sentence_summary`, `label`

**Phase 2 — Self-Reflection:**
- Dedicated reflect prompt receives: original diff (with line numbers) + all generated suggestions
- Can use a different (stronger) model via `model_reasoning` config
- Returns per-suggestion: `suggestion_summary`, `relevant_file`, `relevant_lines_start`, `relevant_lines_end`, `suggestion_score` (0-10), `why`
- Line numbers resolved here — generation doesn't need to emit positions

**Post-reflection filtering:**
- `suggestions_score_threshold=0` (configurable): suggestions below threshold dropped
- `relevant_lines_start < 0` → score=0
- If `existing_code` is in base but not head, and `improved_code` already in head → score=0 (catches already-made changes)
- Results sorted by label group, then by descending score

**Impact display tiers:**
- Score >= 9: "High"
- Score >= 7: "Medium"
- Score < 7: "Low"

### Self-Reflection Pattern (Detailed)

The reflect prompt performs four simultaneous jobs:

1. **Correctness validation**: Check that `existing_code` actually appears in a `__new hunk__` section. Phantom code or contradicted diff → score=0.

2. **`improved_code` coherence check**: Verify the proposed change is consistent with `existing_code`. Inconsistent states → score=0.

3. **Line number resolution**: Map `existing_code` snippet to `relevant_lines_start`/`relevant_lines_end` in the numbered diff. This is how inline GitHub suggestions get positioned — generation works with unnumbered diffs for cleaner output, reflection uses numbered diffs for exact positions.

4. **Impact scoring (0-10)** with explicit caps:
   - High (8-10): only major bugs, security issues
   - Moderate (3-7): minor issues, readability, maintainability
   - Automatic score=0: docstrings/type hints/comments, unused imports, missing imports, more specific exception types, suggestions about entities that may be defined elsewhere
   - Cap at 7: "verify or ensure" suggestions, `existing_code == improved_code`
   - Cap at 8: error handling or type checking suggestions
   - Each suggestion scored independently (no cross-influence)

### Threshold Evolution

| Date | Scoring Rule Change |
|------|-------------------|
| May 2024 | Self-reflection introduced: score 0-10, basic `why` field |
| Sep 2024 | Major rewrite: explicit 4-component description, strict score=0 cases, nuanced high/moderate tiers |
| Oct 2024 | Additional rules: verify/ensure → reduce by 1-2 pts; score=0 for docstrings/type hints/comments |
| Nov 2024 | Line numbers added to reflect: `relevant_lines_start/end` fields |
| Feb 2025 | Impact display tiers: High (>=9) / Medium (>=7) / Low (<7) with configurable thresholds |
| Apr 2025 | Dedicated reasoning model for reflect phase; caps replace reductions (verify-only → cap 7, error handling → cap 8) |

### Lessons for Kenjutsu

1. **Two-phase generate→score is the right architecture.** Generate broadly, score precisely. Don't make the generation prompt do quality filtering — that produces false negatives. Let the scoring pass be the gatekeeper.

2. **Hard-coded zero categories beat vague "be selective" instructions.** Enumerate specific disqualifiers: docstrings → 0, type hints → 0, "verify X" → cap 7. Maintain an explicit automatic-disqualify list.

3. **Score caps are more reliable than score reductions.** "Must not exceed 7" is more predictable than "reduce by 1-2." Caps are compositional across rules.

4. **Resolve positions in the scoring pass, not the generation pass.** Generation emits code text, scoring maps text to line numbers. This simplifies both prompts and the generation model never needs to reason about positions.

5. **Independence assumption prevents cascade scoring bias.** "Assume each suggestion is independent" prevents artificial balancing across findings.

6. **Separate prompts for separate input formats.** The decoupled/non-decoupled split maintains clean variants tuned to different diff representations rather than one over-parameterized prompt.

7. **Use a stronger model for the harder task.** Scoring requires comparing suggestions against code, detecting hallucinations, and applying judgment. A dedicated reasoning model for the reflect phase is a cost/quality optimization.

8. **The "partial codebase" disclaimer must be explicit.** "The absence of a definition in the PR code is NEVER a basis for a suggestion." Kenjutsu findings must include equivalent framing.

---

## /ask — PRQuestions Prompts

### Current Architecture

The simplest of the four tools. Single `[pr_questions_prompt]` section with `system` and `user` strings.

**System prompt:** Role declaration ("designed to answer questions about a Git Pull Request"), behavioral constraints (be informative, constructive, specific; don't stray from questions).

**User prompt:** Jinja2 template injecting `title`, `branch`, `description` (conditional), `language` (conditional), `diff` (via `======` delimiter fencing), and `questions`.

**Notable features:**
- Uses `ModelType.WEAK` — routes to cheaper/faster model
- Image detection: extracts inline image URLs from questions for multimodal queries
- GitLab protection: strips quick actions (`/approve`, `/merge`) from responses
- Conversation history available on `/ask_line` variant but not full `/ask`

### Evolution Timeline

| Date | Change | Why | Impact |
|------|--------|-----|--------|
| 2023-07-06 | Initial release — minimal prompt | First version | Baseline |
| 2023-07-06 | Added "Answer only the questions, don't add unrelated content" | Constrain output scope | Focused responses |
| 2023-08-02 | Added `commit_messages_str` block | Cross-tool normalization | Extra context |
| 2023-12-03 | Removed `commit_messages_str`; switched to `======` delimiters; made `description` conditional | Reduce noise; commit messages didn't help QA | Cleaner prompts |
| 2024-01-09 | "review a Git Pull Request" → "answer questions about a Git Pull Request" | Persona precision | Better alignment |

### Lessons for Kenjutsu

1. **Persona precision matters.** Stating the exact task in the role declaration ("answer questions" not "review PRs") improved alignment. Match the persona to the task.

2. **Remove context that doesn't help.** Commit messages were added then removed — they didn't improve QA answers. Add context only when it demonstrably helps.

3. **Route easy tasks to weaker models.** `/ask` uses `ModelType.WEAK`. Classify queries by complexity at dispatch time and route to cheaper inference.

4. **Use conditional blocks to reduce noise.** `{%- if description %}` prevents empty-string injection. Inject data only when it exists.

5. **Reinforce constraints twice.** "Don't avoid answering" and "You must answer" coexist — double-enforcement reduces hedge behavior.

---

## Edge Case Catalog

### 1. Binary Files
Handled via `bad_extensions` blocklist in `language_extensions.toml`. Covers `bin`, `exe`, `dll`, `so`, `dylib`, `jar`, `war`, `class`, and compiled objects. Files filtered in `filter_bad_extensions()` before diff assembly. The `use_extra_bad_extensions` flag extends the blocklist with `md` and `txt`.

### 2. File Renames/Moves
Tracked via `EDIT_TYPE.RENAMED` enum in `FilePatchInfo`. Renamed files that exceed the token budget appear in the "Additional modified files" overflow section. The `old_filename` field is preserved on the data class for reference.

### 3. Merge Commits
Addressed at trigger level: `push_trigger_ignore_merge_commits = true` prevents the bot from running on merge-commit push events. No special prompt handling — if analysis runs on a merge commit, the diff is processed normally.

### 4. Very Large PRs (Token Overflow)
Two-tier system:
- **Soft threshold** (`OUTPUT_BUFFER_TOKENS_SOFT_THRESHOLD = 1500`): within limit, full diff returned.
- **Compressed diff path**: files sorted by token count (largest first), packed greedily into context window. Overflow files demoted to named lists: "Additional modified files", "Additional added files", "Deleted files".
- **Per-file policy** (`large_patch_policy`): `"clip"` (truncate with 0.9 safety factor) or `"skip"` (drop entirely).
- **Multi-call mode** (`enable_large_pr_handling`): when enabled, processes chunks separately.

### 5. Deletion-Heavy PRs
`handle_patch_deletions()` strips delete-only hunks from compressed diffs. Fully-deleted files catalogued in `deleted_files_list` and appended as filename-only entries in the "Deleted files" section. Saves tokens and prevents model fixation on removed code.

### 6. Multi-Language PRs
`sort_files_by_main_languages()` groups files by detected language, orders groups by repository language share (largest first). Dominant-language files prioritized in diff assembly under tight budgets. Unknown extensions land in "Other" bucket at the end.

### 7. Generated Code Exclusion
`generated_code_ignore.toml` maps framework names to glob patterns: protobuf (`*.pb.go`, `*_pb2.py`), OpenAPI stubs (`__generated__/**`), GraphQL codegen (`*.generated.ts`), gRPC stubs, Go `_gen.go` files. Activated via `ignore_language_framework` config list.

### 8. Lock Files / Dependency Files
Hard-coded in `language_handler.is_valid_file()`: `package-lock.json`, `yarn.lock`, `composer.lock`, `Gemfile.lock`, `poetry.lock` filtered unconditionally. `.lock` and `.lockb` extensions also in `bad_extensions` default list.

### 9. Empty Diffs
`if not patch: continue` guards in all three diff generation paths. Files with no patch content silently skipped. If entire diff is empty, the AI call is skipped entirely with an error log.

### 10. Image / Media Files
Covered by `bad_extensions`: `bmp`, `gif`, `ico`, `jpeg`, `jpg`, `mp3`, `mp4`, `ogg`, `png`, `svg`, `webm`, `woff`, `woff2`, `eot`, `ttf`, `otf`. Never reach diff processing. Exception: on `/ask`, image URLs in the question are extracted for multimodal input.

### 11. Submodule Changes
GitLab has `expand_submodule_diffs = false` (default). Submodule pointer changes are terse single-line SHA diffs; expanding would pull unbounded external code. No special GitHub handling beyond extension/patch filtering.

### 12. Symlinks
No dedicated handling. Symlinks appear as file changes; if target extension is in `bad_extensions` they're filtered, otherwise processed as text. **Gap identified** — symlink changes are one-liners carrying little analytical value.

### 13. PR-Level Ignore Controls
`ignore_pr_title` (regex), `ignore_pr_labels`, `ignore_pr_source_branches`, `ignore_pr_target_branches`, `ignore_pr_authors`, `ignore_repositories` — all checked before any tool runs. Matching PRs silently bypassed at trigger level.

### 14. Patch Extension Skip Types
`patch_extension_skip_types = [".md", ".txt"]` — files with these extensions included in diff count but patches not extended with extra context lines, reducing token spend on documentation changes.

---

## Cross-Cutting Patterns

### Pattern 1: Pydantic-Schema-as-Prompt
The most important and durable pattern. Every tool defines its output as inline Pydantic class definitions within the system prompt. Field names, types, and `Field(description=...)` docstrings together form the output contract. This is more effective than prose instructions because:
- Type annotations constrain output format
- Field descriptions are per-field micro-prompts
- The model treats it as a coding contract, not loose guidance

### Pattern 2: Conditional Template Blocks
Nearly every non-core feature is `{%- if config_flag %}` gated. The prompt schema seen by the model is customized per call. This prevents empty sections confusing the model and lets configuration control output without prompt forking.

### Pattern 3: Delimiter Standardization
All tools migrated from backtick fences to `======` plain delimiters for structural sections (diff, questions, ticket context). This avoids confusion when content itself contains code blocks.

### Pattern 4: Progressive Context Enrichment
User prompts evolved from PR-metadata-only to multi-source context: ticket requirements, AI-generated change summaries, current date, user Q&A, conversation history. Each addition addresses a class of review failures.

### Pattern 5: Tone Calibration
Late addition across tools: explicit prohibition on "Great job", "Thanks for", and "accusatory language." LLM reviews are tonally wrong by default even when technically correct. This needs explicit instruction.

---

## Consolidated Lessons for Kenjutsu Phase 2

### Prompt Architecture
1. **Use Pydantic-schema-as-prompt from day one.** Define Finding, Pattern, Evidence as model definitions. Each field description is a micro-prompt.
2. **Two-phase generate→score for suggestions.** Generate broadly (cheap), score precisely (expensive). Let the scoring pass be the gatekeeper.
3. **Separate tools/prompts per concern.** Review findings, code suggestions, description, QA — each gets its own prompt and schema.
4. **Gate features with conditional template blocks.** Optional sections are `{%- if flag %}` wrapped. No empty sections.

### Output Quality
5. **Quantify all output constraints numerically.** Word counts, list lengths, score ranges. Adjectives ("concise", "brief") don't work.
6. **Hard-coded disqualifier lists beat vague selectivity instructions.** Enumerate what gets score=0.
7. **Score caps over score reductions.** "Must not exceed 7" > "reduce by 1-2".
8. **Field order = output order.** Most important fields first in the schema.

### Prompt Engineering
9. **Behavioral meta-instructions belong in v1.** "What to flag", "how to write comments", confidence thresholds, severity calibration.
10. **Repeat examples for weaker models.** Duplicate YAML example near the generation point.
11. **The diff format is as important as the prompt.** Split hunks, line numbers, clear before/after separation.
12. **Explicit partial-context disclaimers.** "Absence of a definition is NEVER a basis for a finding."

### Configuration
13. **`extra_instructions` is the primary user escape hatch.** Free-text field appended to prompt per analysis type.
14. **Layered file exclusions.** Built-in blocklist → per-repo glob → per-repo regex → framework codegen exclusion.
15. **Configurable finding count.** Default conservatively (3 or fewer).
16. **Config scoping hierarchy.** Org-level defaults → repo-level overrides → per-run overrides.

### Edge Case Handling
17. **Filter before the prompt, not in it.** Binary files, lock files, generated code all excluded before diff assembly.
18. **Clip vs. skip policy for large files.** Expose as user-configurable, not hard-coded.
19. **Language-aware diff ordering.** Dominant language first under tight token budgets.
20. **Delete-only hunks stripped from compressed diffs.** Don't waste tokens on removed code.

---

## License Compliance Notes

- All findings describe patterns, techniques, and architectural decisions — not verbatim code.
- No TOML content has been copied from post-May-2025 commits (AGPL-3.0 boundary).
- Prompt engineering techniques (structured output, self-reflection, confidence scoring) are not copyrightable.
- Commit hashes and dates are factual references, not creative content.
