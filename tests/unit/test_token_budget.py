"""Unit tests for kenjutsu.diff.budget — token budget management.

Tests written before implementation (TDD). Each test covers exactly one behavior.
"""

from unittest.mock import patch

from kenjutsu.diff.budget import (
    count_tokens,
    fit_to_budget,
    input_token_budget,
    split_into_passes,
)
from kenjutsu.diff.models import ChangeType, Hunk, HunkLine, PatchFile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KIND_MAP = {"add": ChangeType.ADD, "del": ChangeType.DELETE, "context": ChangeType.CONTEXT}


def make_hunk(lines: list[tuple[str, str]], old_start: int = 1, new_start: int = 1) -> Hunk:
    """Build a Hunk from (kind, text) tuples. kind: 'add', 'del', 'context'."""
    hunk_lines = [
        HunkLine(change_type=_KIND_MAP[k], content=t, old_lineno=None, new_lineno=None)
        for k, t in lines
    ]
    old_count = sum(1 for k, _ in lines if k in ("del", "context"))
    new_count = sum(1 for k, _ in lines if k in ("add", "context"))
    return Hunk(
        old_start=old_start,
        old_count=old_count,
        new_start=new_start,
        new_count=new_count,
        lines=hunk_lines,
    )


def make_patch(path: str, hunks: list[Hunk]) -> PatchFile:
    """Build a PatchFile from a path and list of hunks."""
    return PatchFile(old_path=path, new_path=path, hunks=hunks)


# ---------------------------------------------------------------------------
# count_tokens
# ---------------------------------------------------------------------------


def test_count_tokens_delegates_to_litellm_token_counter() -> None:
    """count_tokens must call litellm.token_counter with (model=, text=)."""
    with patch("litellm.token_counter", return_value=42) as mock_counter:
        result = count_tokens("hello world", "gpt-4")

    mock_counter.assert_called_once_with(model="gpt-4", text="hello world")
    assert result == 42


# ---------------------------------------------------------------------------
# input_token_budget
# ---------------------------------------------------------------------------


def test_input_token_budget_reserves_ten_percent_for_output() -> None:
    """gpt-4 has 8192 context; 90% should be available for input."""
    budget = input_token_budget("gpt-4")
    assert budget == int(8192 * 0.9)  # 7372


def test_input_token_budget_uses_default_for_unknown_model() -> None:
    """Unknown models fall back to 8192-token default context."""
    budget = input_token_budget("some-future-model-xyz")
    assert budget == int(8192 * 0.9)


def test_input_token_budget_claude_model() -> None:
    """Claude Sonnet has 200k context; 90% = 180000."""
    budget = input_token_budget("claude-sonnet-4-6")
    assert budget == int(200_000 * 0.9)


# ---------------------------------------------------------------------------
# fit_to_budget
# ---------------------------------------------------------------------------


def test_fit_to_budget_empty_list_returns_empty() -> None:
    """fit_to_budget with no hunks returns an empty list without errors."""
    result = fit_to_budget([], "gpt-4")
    assert result == []


def test_fit_to_budget_small_diff_returns_all_hunks() -> None:
    """When all hunks fit within budget, every hunk is returned intact."""
    hunks = [
        make_hunk([("add", "+foo"), ("context", " bar")]),
        make_hunk([("del", "-baz")]),
    ]
    with patch("kenjutsu.diff.budget.count_tokens", return_value=10):
        result = fit_to_budget(hunks, "gpt-4")

    assert result == hunks


def test_fit_to_budget_falls_back_to_changed_lines_when_full_hunk_exceeds_budget() -> None:
    """When a hunk's full text exceeds budget, include only changed lines.

    Budget = 7372 (gpt-4).
    hunk1 full = 5000 → fits. used = 5000.
    hunk2 full = 3000 → exceeds (5000+3000=8000 > 7372).
    hunk2 changed = 1000 → fits (5000+1000=6000 ≤ 7372).
    Expected: 2 hunks; hunk2 contains only its add/del lines.
    """
    hunk1 = make_hunk([("add", "+change"), ("context", " ctx")])
    hunk2 = make_hunk([("add", "+important"), ("context", " ctx1"), ("context", " ctx2")])

    # Side effects: hunk1_full=5000, hunk2_full=3000, hunk2_changed=1000
    with patch("kenjutsu.diff.budget.count_tokens", side_effect=[5000, 3000, 1000]):
        result = fit_to_budget([hunk1, hunk2], "gpt-4")

    assert len(result) == 2
    assert result[0] == hunk1
    # Trimmed hunk has only the add line
    assert all(ln.change_type in (ChangeType.ADD, ChangeType.DELETE) for ln in result[1].lines)
    assert len(result[1].lines) == 1


def test_fit_to_budget_skips_hunk_when_even_changed_lines_exceed_budget() -> None:
    """When a hunk's changed lines alone exceed the remaining budget, skip it.

    Budget = 7372 (gpt-4).
    hunk1 full = 6000 → fits. used = 6000.
    hunk2 full = 2000 → exceeds (6000+2000=8000 > 7372).
    hunk2 changed = 2000 → exceeds (6000+2000=8000 > 7372) → skip.
    Expected: only hunk1 returned.
    """
    hunk1 = make_hunk([("add", "+big change")])
    hunk2 = make_hunk([("add", "+another"), ("context", " ctx")])

    with patch("kenjutsu.diff.budget.count_tokens", side_effect=[6000, 2000, 2000]):
        result = fit_to_budget([hunk1, hunk2], "gpt-4")

    assert len(result) == 1
    assert result[0] == hunk1


def test_fit_to_budget_single_hunk_fits_completely() -> None:
    """Single hunk within budget is returned as-is."""
    hunk = make_hunk([("add", "+x"), ("context", " y")])
    with patch("kenjutsu.diff.budget.count_tokens", return_value=100):
        result = fit_to_budget([hunk], "gpt-4")

    assert result == [hunk]


# ---------------------------------------------------------------------------
# split_into_passes
# ---------------------------------------------------------------------------


def test_split_into_passes_empty_patches_returns_empty_list() -> None:
    """No patches → no passes."""
    result = split_into_passes([], "gpt-4")
    assert result == []


def test_split_into_passes_patches_with_no_hunks_returns_empty_list() -> None:
    """Patches that contain no hunks → no passes."""
    result = split_into_passes([make_patch("a.py", [])], "gpt-4")
    assert result == []


def test_split_into_passes_small_diff_produces_single_pass() -> None:
    """When total tokens fit within budget, all hunks go into one pass."""
    hunk_a = make_hunk([("add", "+foo")])
    hunk_b = make_hunk([("add", "+bar")])
    patches = [make_patch("a.py", [hunk_a]), make_patch("b.py", [hunk_b])]

    with patch("kenjutsu.diff.budget.count_tokens", return_value=100):
        passes = split_into_passes(patches, "gpt-4")

    assert len(passes) == 1
    assert len(passes[0]) == 2


def test_split_into_passes_large_diff_splits_into_multiple_passes() -> None:
    """Each hunk that won't fit with the current pass starts a new one.

    Budget = 7372 (gpt-4). Each hunk = 4000 tokens.
    hunk1 → pass 1 (used=4000).
    hunk2 → 4000+4000=8000 > 7372 → new pass 2 (used=4000).
    hunk3 → 4000+4000=8000 > 7372 → new pass 3 (used=4000).
    Expected: 3 passes, one hunk each.
    """
    hunks = [
        make_hunk([("add", "+foo")]),
        make_hunk([("add", "+bar")]),
        make_hunk([("add", "+baz")]),
    ]
    patches = [make_patch(f"{chr(97 + i)}.py", [h]) for i, h in enumerate(hunks)]

    with patch("kenjutsu.diff.budget.count_tokens", side_effect=[4000, 4000, 4000]):
        passes = split_into_passes(patches, "gpt-4")

    assert len(passes) == 3
    assert [len(p) for p in passes] == [1, 1, 1]


def test_split_into_passes_single_hunk_produces_one_pass() -> None:
    """A diff with a single hunk always produces exactly one pass."""
    hunk = make_hunk([("add", "+x")])
    patches = [make_patch("a.py", [hunk])]

    with patch("kenjutsu.diff.budget.count_tokens", return_value=10):
        passes = split_into_passes(patches, "gpt-4")

    assert len(passes) == 1
    assert passes[0] == [hunk]


def test_split_into_passes_preserves_hunk_order_within_passes() -> None:
    """Hunk ordering across patches must be preserved in the output passes."""
    hunks = [
        make_hunk([("add", "+1")]),
        make_hunk([("add", "+2")]),
    ]
    patches = [make_patch("a.py", hunks)]

    with patch("kenjutsu.diff.budget.count_tokens", return_value=100):
        passes = split_into_passes(patches, "gpt-4")

    assert passes[0] == hunks
