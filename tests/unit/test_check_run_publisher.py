"""Unit tests for Check Run publisher helpers.

Tests annotation formatting, batching, summary building, and publishing
logic — all without hitting the GitHub API.
"""

from __future__ import annotations

from kenjutsu.models.findings import (
    Category,
    Confidence,
    Finding,
    Origin,
    Publishability,
    Severity,
)
from kenjutsu.publisher.check_run import (
    ANNOTATION_BATCH_SIZE,
    _batch_annotations,
    _build_summary,
    _build_title,
    _determine_conclusion,
    _finding_to_annotation,
    _is_inline_publishable,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(**overrides: object) -> Finding:
    defaults: dict[str, object] = {
        "file_path": "src/auth.py",
        "line_start": 10,
        "line_end": 12,
        "origin": Origin.LLM,
        "confidence": Confidence.HIGH,
        "severity": Severity.WARNING,
        "category": Category.BUG,
        "description": "Potential null dereference",
    }
    defaults.update(overrides)
    return Finding(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _is_inline_publishable
# ---------------------------------------------------------------------------


class TestIsInlinePublishable:
    def test_publish_finding_is_publishable(self) -> None:
        f = _make_finding(publishability=Publishability.PUBLISH)
        assert _is_inline_publishable(f) is True

    def test_redact_and_publish_is_publishable(self) -> None:
        f = _make_finding(publishability=Publishability.REDACT_AND_PUBLISH)
        assert _is_inline_publishable(f) is True

    def test_suppress_is_not_publishable(self) -> None:
        f = _make_finding(publishability=Publishability.SUPPRESS)
        assert _is_inline_publishable(f) is False

    def test_audit_only_is_not_publishable(self) -> None:
        f = _make_finding(publishability=Publishability.AUDIT_ONLY)
        assert _is_inline_publishable(f) is False

    def test_predictive_origin_is_never_inline(self) -> None:
        """Predictive findings must never appear as inline annotations."""
        f = _make_finding(origin=Origin.PREDICTIVE, publishability=Publishability.PUBLISH)
        assert _is_inline_publishable(f) is False

    def test_deterministic_origin_is_publishable(self) -> None:
        f = _make_finding(origin=Origin.DETERMINISTIC)
        assert _is_inline_publishable(f) is True

    def test_graph_origin_is_publishable(self) -> None:
        f = _make_finding(origin=Origin.GRAPH)
        assert _is_inline_publishable(f) is True


# ---------------------------------------------------------------------------
# _finding_to_annotation
# ---------------------------------------------------------------------------


class TestFindingToAnnotation:
    def test_critical_maps_to_failure(self) -> None:
        f = _make_finding(severity=Severity.CRITICAL)
        ann = _finding_to_annotation(f)
        assert ann["annotation_level"] == "failure"

    def test_warning_maps_to_warning(self) -> None:
        f = _make_finding(severity=Severity.WARNING)
        ann = _finding_to_annotation(f)
        assert ann["annotation_level"] == "warning"

    def test_suggestion_maps_to_notice(self) -> None:
        f = _make_finding(severity=Severity.SUGGESTION)
        ann = _finding_to_annotation(f)
        assert ann["annotation_level"] == "notice"

    def test_file_path_and_lines_are_set(self) -> None:
        f = _make_finding(file_path="src/utils.py", line_start=5, line_end=8)
        ann = _finding_to_annotation(f)
        assert ann["path"] == "src/utils.py"
        assert ann["start_line"] == 5
        assert ann["end_line"] == 8

    def test_description_becomes_message(self) -> None:
        f = _make_finding(description="Missing null check")
        ann = _finding_to_annotation(f)
        assert "Missing null check" in ann["message"]

    def test_suggestion_appended_to_message(self) -> None:
        f = _make_finding(description="Missing null check", suggestion="Add `if x is None` guard")
        ann = _finding_to_annotation(f)
        assert "Missing null check" in ann["message"]
        assert "Add `if x is None` guard" in ann["message"]

    def test_no_suggestion_message_clean(self) -> None:
        f = _make_finding(description="Issue here", suggestion=None)
        ann = _finding_to_annotation(f)
        assert ann["message"] == "Issue here"


# ---------------------------------------------------------------------------
# _batch_annotations
# ---------------------------------------------------------------------------


class TestBatchAnnotations:
    def test_empty_list_returns_empty(self) -> None:
        assert _batch_annotations([]) == []

    def test_single_item_one_batch(self) -> None:
        batches = _batch_annotations([{"a": 1}])
        assert len(batches) == 1
        assert batches[0] == [{"a": 1}]

    def test_exactly_batch_size_is_one_batch(self) -> None:
        items = [{"i": i} for i in range(ANNOTATION_BATCH_SIZE)]
        batches = _batch_annotations(items)
        assert len(batches) == 1
        assert len(batches[0]) == ANNOTATION_BATCH_SIZE

    def test_one_over_batch_size_is_two_batches(self) -> None:
        items = [{"i": i} for i in range(ANNOTATION_BATCH_SIZE + 1)]
        batches = _batch_annotations(items)
        assert len(batches) == 2
        assert len(batches[0]) == ANNOTATION_BATCH_SIZE
        assert len(batches[1]) == 1

    def test_no_items_lost_across_batches(self) -> None:
        count = ANNOTATION_BATCH_SIZE * 3 + 7
        items = [{"i": i} for i in range(count)]
        batches = _batch_annotations(items)
        flat = [item for batch in batches for item in batch]
        assert len(flat) == count

    def test_each_batch_at_most_batch_size(self) -> None:
        items = [{"i": i} for i in range(200)]
        for batch in _batch_annotations(items):
            assert len(batch) <= ANNOTATION_BATCH_SIZE


# ---------------------------------------------------------------------------
# _build_title
# ---------------------------------------------------------------------------


class TestBuildTitle:
    def test_title_includes_finding_count(self) -> None:
        findings = [_make_finding() for _ in range(3)]
        title = _build_title(findings, duration_seconds=5.0)
        assert "3" in title

    def test_title_includes_duration(self) -> None:
        title = _build_title([], duration_seconds=12.5)
        assert "12.5" in title

    def test_suppressed_findings_not_counted(self) -> None:
        visible = [_make_finding(publishability=Publishability.PUBLISH) for _ in range(2)]
        hidden = [_make_finding(publishability=Publishability.SUPPRESS) for _ in range(5)]
        title = _build_title(visible + hidden, duration_seconds=1.0)
        assert "2" in title

    def test_predictive_findings_not_counted(self) -> None:
        defect = _make_finding(origin=Origin.LLM)
        predictive = _make_finding(origin=Origin.PREDICTIVE)
        title = _build_title([defect, predictive], duration_seconds=1.0)
        assert "1" in title


# ---------------------------------------------------------------------------
# _build_summary
# ---------------------------------------------------------------------------


class TestBuildSummary:
    def test_summary_includes_finding_count(self) -> None:
        findings = [_make_finding(severity=Severity.CRITICAL) for _ in range(2)]
        summary = _build_summary(findings, predictive_warnings=[], duration_seconds=3.0)
        assert "2" in summary

    def test_summary_includes_duration(self) -> None:
        summary = _build_summary([], predictive_warnings=[], duration_seconds=7.2)
        assert "7.2" in summary

    def test_predictive_warnings_section_present_when_given(self) -> None:
        pw = _make_finding(origin=Origin.PREDICTIVE, category=Category.CO_CHANGE, description="B changes with A")
        summary = _build_summary([], predictive_warnings=[pw], duration_seconds=1.0)
        assert "Prediction" in summary
        assert "B changes with A" in summary

    def test_predictive_warnings_section_absent_when_empty(self) -> None:
        summary = _build_summary([], predictive_warnings=[], duration_seconds=1.0)
        assert "Prediction" not in summary

    def test_predictive_findings_not_in_inline_count(self) -> None:
        predictive = _make_finding(origin=Origin.PREDICTIVE)
        summary = _build_summary([predictive], predictive_warnings=[predictive], duration_seconds=1.0)
        # 0 inline findings — predictive is only in the summary section
        assert "0" in summary

    def test_severity_breakdown_present(self) -> None:
        findings = [
            _make_finding(severity=Severity.CRITICAL),
            _make_finding(severity=Severity.WARNING),
            _make_finding(severity=Severity.SUGGESTION),
        ]
        summary = _build_summary(findings, predictive_warnings=[], duration_seconds=2.0)
        assert "Critical" in summary
        assert "Warning" in summary
        assert "Suggestion" in summary


# ---------------------------------------------------------------------------
# _determine_conclusion
# ---------------------------------------------------------------------------


class TestDetermineConclusion:
    def test_no_findings_is_success(self) -> None:
        assert _determine_conclusion([]) == "success"

    def test_only_suggestions_is_neutral(self) -> None:
        f = _make_finding(severity=Severity.SUGGESTION)
        assert _determine_conclusion([f]) == "neutral"

    def test_only_warnings_is_neutral(self) -> None:
        f = _make_finding(severity=Severity.WARNING)
        assert _determine_conclusion([f]) == "neutral"

    def test_critical_finding_is_failure(self) -> None:
        f = _make_finding(severity=Severity.CRITICAL)
        assert _determine_conclusion([f]) == "failure"

    def test_suppressed_critical_is_not_failure(self) -> None:
        f = _make_finding(severity=Severity.CRITICAL, publishability=Publishability.SUPPRESS)
        assert _determine_conclusion([f]) == "success"

    def test_predictive_critical_is_not_failure(self) -> None:
        """Predictive findings never drive conclusion."""
        f = _make_finding(origin=Origin.PREDICTIVE, severity=Severity.CRITICAL)
        assert _determine_conclusion([f]) == "success"
