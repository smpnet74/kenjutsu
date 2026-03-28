"""Token budget management for diff context fitting.

Responsibilities:
- Count tokens via LiteLLM (model-aware, works for Claude, GPT-4, etc.)
- Compute the available input budget (model context minus 10% output reserve)
- Greedy fill: pack hunks within budget, changed lines (add/del) take priority over
  context lines when a hunk must be trimmed to fit
- Multi-pass split: partition large diffs into passes that each fit within budget
"""

from __future__ import annotations

from kenjutsu.diff.models import ChangeType, Hunk, PatchFile

# ---------------------------------------------------------------------------
# Model context registry
# ---------------------------------------------------------------------------

#: Known model context window sizes (in tokens). New models can be appended here
#: without touching any other code. Unknown models fall back to DEFAULT_CONTEXT_SIZE.
MODEL_CONTEXT_SIZES: dict[str, int] = {
    # Claude 4.x
    "claude-opus-4-6": 200_000,
    "claude-sonnet-4-6": 200_000,
    # Claude 3.x
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
    "claude-3-opus-20240229": 200_000,
    "claude-3-haiku-20240307": 200_000,
    # OpenAI
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 16_385,
}

OUTPUT_RESERVE_FRACTION: float = 0.10
DEFAULT_CONTEXT_SIZE: int = 8_192

# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def model_context_size(model: str) -> int:
    """Return the full context window size for *model*."""
    return MODEL_CONTEXT_SIZES.get(model, DEFAULT_CONTEXT_SIZE)


def input_token_budget(model: str) -> int:
    """Return the number of tokens available for input.

    Reserves OUTPUT_RESERVE_FRACTION (10 %) of the context window for the
    model's output so the prompt is never so large that the response is cut off.
    """
    return int(model_context_size(model) * (1.0 - OUTPUT_RESERVE_FRACTION))


def count_tokens(text: str, model: str) -> int:
    """Count tokens in *text* for *model* using LiteLLM's token_counter.

    LiteLLM dispatches to the correct tokenizer per provider (tiktoken for
    OpenAI, Anthropic tokenizer for Claude, etc.) so the count is accurate
    across model families.
    """
    from litellm import token_counter  # imported lazily to keep startup fast

    return token_counter(model=model, text=text)


def _hunk_to_text(hunk: Hunk, changed_only: bool = False) -> str:
    """Render *hunk* lines as a single string.

    When *changed_only* is True only add/del lines are included — this is used
    when a full hunk exceeds the remaining budget but changed lines may still fit.
    """
    if changed_only:
        lines = [line.content for line in hunk.lines if line.change_type in (ChangeType.ADD, ChangeType.DELETE)]
    else:
        lines = [line.content for line in hunk.lines]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fit_to_budget(hunks: list[Hunk], model: str) -> list[Hunk]:
    """Pack hunks into the input token budget using a greedy fill strategy.

    For each hunk (in order):
    1. Try to include the full hunk (changed + context lines).
    2. If it doesn't fit, try including only the changed lines (add/del).
    3. If even changed lines don't fit, skip the hunk entirely.

    Returns a list of hunks (some potentially trimmed to changed-only lines)
    that collectively fit within ``input_token_budget(model)``.
    """
    budget = input_token_budget(model)
    result: list[Hunk] = []
    used = 0

    for hunk in hunks:
        full_text = _hunk_to_text(hunk)
        full_tokens = count_tokens(full_text, model) if full_text else 0

        if used + full_tokens <= budget:
            result.append(hunk)
            used += full_tokens
            continue

        # Full hunk exceeds remaining budget — try changed lines only.
        changed_text = _hunk_to_text(hunk, changed_only=True)
        if not changed_text:
            continue

        changed_tokens = count_tokens(changed_text, model)
        if used + changed_tokens <= budget:
            changed_lines = [line for line in hunk.lines if line.change_type in (ChangeType.ADD, ChangeType.DELETE)]
            trimmed = Hunk(
                old_start=hunk.old_start,
                old_count=sum(1 for ln in changed_lines if ln.change_type == ChangeType.DELETE),
                new_start=hunk.new_start,
                new_count=sum(1 for ln in changed_lines if ln.change_type == ChangeType.ADD),
                lines=changed_lines,
                section_header=hunk.section_header,
            )
            result.append(trimmed)
            used += changed_tokens

    return result


def split_into_passes(patches: list[PatchFile], model: str) -> list[list[Hunk]]:
    """Split all hunks across patches into passes that each fit within budget.

    Hunks are processed in file order. When adding the next hunk would exceed
    the budget, the current pass is sealed and a new one begins.

    Returns a list of passes. Each pass is a list of Hunk objects. Returns an
    empty list when there are no hunks to process.
    """
    budget = input_token_budget(model)
    all_hunks = [hunk for patch in patches for hunk in patch.hunks]

    if not all_hunks:
        return []

    passes: list[list[Hunk]] = []
    current_pass: list[Hunk] = []
    current_tokens = 0

    for hunk in all_hunks:
        text = _hunk_to_text(hunk)
        tokens = count_tokens(text, model) if text else 0

        if current_pass and current_tokens + tokens > budget:
            passes.append(current_pass)
            current_pass = [hunk]
            current_tokens = tokens
        else:
            current_pass.append(hunk)
            current_tokens += tokens

    if current_pass:
        passes.append(current_pass)

    return passes
