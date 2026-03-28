# Appendix: Chronological Change Log — PR-Agent Prompt Evolution

- **Status:** review
- **Author:** Research Specialist
- **Date:** 2026-03-27
- **Issue:** DEM-158
- **Parent:** DEM-139

---

This appendix provides a chronological view of significant prompt changes across all four PR-Agent tools. Only changes that affected prompt structure, output schema, or behavioral instructions are included — minor typo fixes and formatting-only commits are omitted.

## Timeline

| Date | Tool | Commit | Change Summary |
|------|------|--------|---------------|
| 2023-07-06 | /ask | `4b4d91df` | Initial release — minimal QA prompt |
| 2023-07-06 | /ask | `e53ae712` | Added scope constraint: "answer only the questions" |
| 2023-10-23 | /describe | `fa244132` | Custom labels via `{{ custom_labels }}` template variable |
| 2023-11-26 | /review | `690c1136` | Added code suggestions guidelines block; focus-on-new-lines moved to top |
| 2023-11-26 | /describe | `0326b7e4` | Conditional blocks; `=====` delimiters |
| 2023-12-03 | /review | `2d726edb` | Standardized `======` fence delimiters across prompts |
| 2023-12-03 | /describe | `5c01f97f` | Added `FileWalkthrough` class; explicit task description |
| 2023-12-04 | /describe | `d2a129fe` → `863eb010` | Tried label-grouped files → abandoned same day for per-file approach |
| 2023-12-06 | /describe | `4b073b32` | **Pivot**: `FileDescription` (file → label + summary) becomes stable architecture |
| 2024-01-05 | /describe | `3628786a` | "Return label member value, not enum name" |
| 2024-01-09 | /ask | `e56c443f` | Persona refined: "answer questions about" not "review" |
| 2024-01-21 | /describe | `8d513e07` | Added `changes_title` field (5-10 words per file) |
| 2024-02-08 | /review | `ddb89a74` | **Major**: Removed narrative "PR Analysis" section entirely |
| 2024-03-01 | /review | `35315c07` | **Major**: Schema switched from YAML to Pydantic class definitions |
| 2024-03-09 | /review | `8324e9a3` | Added `can_be_split` field with `SubPR` model |
| 2024-04-02 | /review | `e589dcb4` | Added `possible_issues` free-text field |
| 2024-05-10 | /improve | `1ebc20b7` | **Major**: Self-reflection introduced — `reflect_prompts.toml`, score 0-10 |
| 2024-05-19 | /review | `5a8ce252` | `num_max_findings` configurable |
| 2024-06-04 | /review | `4d96d11b` | `security_concerns` gated on `require_security_review` flag |
| 2024-06-09 | /review | `9c8bc6c8` | `possible_issues` → `key_issues_to_review`; effort: `str` → `int` |
| 2024-07-14 | /review | `5d6e1de1` | **Major**: `key_issues_to_review` → `List[KeyIssuesComponentLink]` with structured objects |
| 2024-08-20 | /improve | `8fb9b8ed` | Generation: "don't repeat changes already present in PR" |
| 2024-09-07 | /review | `8706f643` | AI metadata support in diff context |
| 2024-09-25 | /improve | `6f14f9c8` | **Major**: Self-reflection rewritten — professional framing, strict score=0 cases, nuanced tiers |
| 2024-10-01 | /improve | `dfa4f22b` | Dual publishing mode (table + inline) |
| 2024-10-07 | /improve | `4b05a3e8` | Additional scoring rules: verify/ensure → reduce 1-2; docstrings/type hints → 0 |
| 2024-10-10 | /review | `76d95bb6` | **Major**: `TicketCompliance` model added; ticket context in user prompt |
| 2024-10-10 | /describe | `76d95bb6` | Related tickets block added to user prompt |
| 2024-11-03 | /improve | `ef324128` | **Major**: Line numbers added to reflect — `relevant_lines_start/end` |
| 2024-12-19 | /review | `7e8361b5` | Collapsible code snippets; `referenced_variables` |
| 2024-12-25 | /review | `495c1ebe` | **Major**: All code suggestion fields removed from review prompt |
| 2024-12-29 | /describe | `e95920c5` | Simplification: removed `language` field; file cap 15→20 |
| 2024-12-31 | /describe | `4a1b0421` | Quantified: "up to four bullet points, each up to 8 words" |
| 2025-01-02 | /describe | `53180472` | `duplicate_prompt_examples` option for weaker models |
| 2025-01-19 | /review | `e7f874a4` | Explicit diff format documentation; partial-context guidance |
| 2025-01-26 | /review | `50c52e32` | `requires_further_human_verification` in ticket compliance |
| 2025-02-05 | /improve | `69f19f1a` | Impact display tiers: High (>=9) / Medium (>=7) / Low |
| 2025-02-20 | /review | `a07f6855` | Current date added to PR metadata |
| 2025-03-11 | /improve | `d16012a5` | Decoupled/non-decoupled prompt split; reflect file restructured |
| 2025-03-30 | /review | `afa4adcb` | Partial code block guidance (opening braces) |
| 2025-04-27 | /improve | `f53bd524` | **Major**: Dedicated reasoning model (`model_reasoning`) for reflect phase |
| 2025-04-27 | /improve | `60a887ff` | Scoring: caps replace reductions (verify→cap 7, errors→cap 8) |
| 2025-05-24 | /review | `788c0c12` | TODO scanning field added |
| 2025-05-25 | /describe | `7273c9c0` | **Major**: Mermaid diagram field added (7 fixup commits same day) |
| 2025-06-17 | /review | `7c02678b` | `TodoSection` simplified to single `line_number` |
| 2025-06-24 | /describe | `ead2c927` | Diagram enabled by default |
| 2025-08-22 | /review | `5fc466bf` | `ContributionTimeCostEstimate` model added |
| 2026-03-23 | /review | `42d55d41` | **Major**: "Determining what to flag" + "Constructing comments" behavioral sections |

## Key Inflection Points

1. **March 2024 — Pydantic schema adoption.** The switch from YAML schema descriptions to inline Pydantic class definitions set the template for all subsequent prompt work. Every tool converged on this pattern.

2. **May 2024 — Self-reflection introduced.** The two-phase generate→score pattern for `/improve` fundamentally changed the quality model from "write good prompts" to "generate, then evaluate."

3. **July 2024 — Structured issue objects.** `key_issues_to_review` becoming `List[KeyIssuesComponentLink]` made review findings machine-readable and line-addressable for the first time.

4. **December 2024 — Concern separation.** Removing code suggestions from the review prompt completed the architectural separation into distinct, focused tools.

5. **April 2025 — Reasoning model split.** Using a dedicated, potentially stronger model for scoring (while keeping a faster model for generation) introduced a cost/quality optimization layer.

6. **March 2026 — Behavioral meta-instructions.** The latest inflection: explicit instructions about *what qualifies as a finding* and *how to write it*, addressing the noise problem that structured schemas alone could not solve.
