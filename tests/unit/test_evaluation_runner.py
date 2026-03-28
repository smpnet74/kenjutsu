"""Unit tests for the evaluation runner.

Covers:
- Finding matching (TP/FP/miss classification)
- Line-range overlap logic
- Metrics computation (Appendix D)
- Report generation (JSON + markdown)
"""

from __future__ import annotations

import json
import statistics
from typing import TYPE_CHECKING

import pytest

from kenjutsu.evaluation.runner import (
    _DEFECT_CATEGORIES,
    AnnotatedFinding,
    EvalMetrics,
    EvalResult,
    _line_ranges_overlap,
    compute_metrics,
    match_findings,
    write_report,
)
from kenjutsu.models import Category, Confidence, Finding, Origin, Publishability, Severity

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------


def _finding(
    file_path: str = "src/auth.py",
    line_start: int = 42,
    line_end: int = 42,
    category: Category = Category.BUG,
    confidence: Confidence = Confidence.HIGH,
    severity: Severity = Severity.WARNING,
    origin: Origin = Origin.LLM,
    description: str = "potential null dereference",
) -> Finding:
    return Finding(
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        origin=origin,
        confidence=confidence,
        severity=severity,
        category=category,
        publishability=Publishability.PUBLISH,
        description=description,
    )


def _annotated(
    file_path: str = "src/auth.py",
    line_range: tuple[int, int] = (42, 42),
    category: Category = Category.BUG,
    severity: Severity = Severity.WARNING,
    confidence: Confidence = Confidence.VERIFIED,
    description: str = "potential null dereference",
) -> AnnotatedFinding:
    return AnnotatedFinding(
        file_path=file_path,
        line_range=line_range,
        category=category,
        severity=severity,
        confidence=confidence,
        description=description,
    )


def _result(
    pr_id: str = "repo_42",
    variant: str = "structural",
    findings_produced: list[Finding] | None = None,
    expected_findings: list[AnnotatedFinding] | None = None,
    true_positives: list[Finding] | None = None,
    false_positives: list[Finding] | None = None,
    missed: list[AnnotatedFinding] | None = None,
    latency_ms: int = 10_000,
    tokens_in: int = 1_000,
    tokens_out: int = 200,
    cost_usd: float = 0.01,
) -> EvalResult:
    return EvalResult(
        pr_id=pr_id,
        variant=variant,
        findings_produced=findings_produced or [],
        expected_findings=expected_findings or [],
        true_positives=true_positives or [],
        false_positives=false_positives or [],
        missed=missed or [],
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
    )


# ---------------------------------------------------------------------------
# _line_ranges_overlap
# ---------------------------------------------------------------------------


class TestLineRangesOverlap:
    def test_exact_match(self) -> None:
        assert _line_ranges_overlap((42, 42), (42, 42))

    def test_produced_fully_inside_expected(self) -> None:
        assert _line_ranges_overlap((45, 50), (40, 60))

    def test_expected_fully_inside_produced(self) -> None:
        assert _line_ranges_overlap((40, 60), (45, 50))

    def test_partial_overlap(self) -> None:
        assert _line_ranges_overlap((40, 55), (50, 65))

    def test_no_overlap_far_apart(self) -> None:
        # 200 lines apart, tolerance=5 is not enough
        assert not _line_ranges_overlap((10, 15), (200, 210))

    def test_adjacent_no_overlap_beyond_tolerance(self) -> None:
        # produced ends at 30, expected starts at 40 — gap of 10, tolerance=5
        assert not _line_ranges_overlap((20, 30), (40, 50), tolerance=5)

    def test_within_tolerance(self) -> None:
        # produced ends at 35, expected starts at 40 — gap of 5, tolerance=5
        assert _line_ranges_overlap((30, 35), (40, 50), tolerance=5)

    def test_tolerance_zero_exact_required(self) -> None:
        assert not _line_ranges_overlap((30, 35), (40, 50), tolerance=0)

    def test_tolerance_zero_adjacent_no_overlap(self) -> None:
        assert not _line_ranges_overlap((30, 39), (40, 50), tolerance=0)

    def test_tolerance_zero_touching_matches(self) -> None:
        assert _line_ranges_overlap((30, 40), (40, 50), tolerance=0)


# ---------------------------------------------------------------------------
# match_findings
# ---------------------------------------------------------------------------


class TestMatchFindings:
    def test_single_tp(self) -> None:
        f = _finding()
        ann = _annotated()
        tp, fp, missed = match_findings([f], [ann])
        assert tp == [f]
        assert fp == []
        assert missed == []

    def test_single_fp(self) -> None:
        f = _finding(file_path="src/auth.py", line_start=42, line_end=42)
        ann = _annotated(file_path="src/other.py")  # different file
        tp, fp, missed = match_findings([f], [ann])
        assert tp == []
        assert fp == [f]
        assert missed == [ann]

    def test_single_miss(self) -> None:
        ann = _annotated()
        tp, fp, missed = match_findings([], [ann])
        assert tp == []
        assert fp == []
        assert missed == [ann]

    def test_category_mismatch_causes_fp(self) -> None:
        f = _finding(category=Category.SECURITY)
        ann = _annotated(category=Category.BUG)
        tp, fp, missed = match_findings([f], [ann])
        assert tp == []
        assert fp == [f]
        assert missed == [ann]

    def test_line_range_within_tolerance_matches(self) -> None:
        f = _finding(line_start=44, line_end=44)  # 2 lines off from annotated 42
        ann = _annotated(line_range=(42, 42))
        tp, fp, _missed = match_findings([f], [ann])
        assert len(tp) == 1
        assert len(fp) == 0

    def test_line_range_outside_tolerance_misses(self) -> None:
        f = _finding(line_start=100, line_end=100)
        ann = _annotated(line_range=(42, 42))
        tp, fp, missed = match_findings([f], [ann])
        assert tp == []
        assert fp == [f]
        assert missed == [ann]

    def test_each_expected_matched_at_most_once(self) -> None:
        # Two identical findings should only consume one expected annotation
        f1 = _finding()
        f2 = _finding()
        ann = _annotated()
        tp, fp, missed = match_findings([f1, f2], [ann])
        assert len(tp) == 1
        assert len(fp) == 1
        assert missed == []

    def test_multiple_prs_all_match(self) -> None:
        findings = [
            _finding(file_path="a.py", line_start=10, line_end=10, category=Category.BUG),
            _finding(file_path="b.py", line_start=20, line_end=20, category=Category.SECURITY),
        ]
        annotations = [
            _annotated(file_path="a.py", line_range=(10, 10), category=Category.BUG),
            _annotated(file_path="b.py", line_range=(20, 20), category=Category.SECURITY),
        ]
        tp, fp, missed = match_findings(findings, annotations)
        assert len(tp) == 2
        assert fp == []
        assert missed == []

    def test_empty_inputs(self) -> None:
        tp, fp, missed = match_findings([], [])
        assert tp == fp == missed == []

    def test_no_expected_all_fp(self) -> None:
        findings = [_finding(), _finding(file_path="src/other.py")]
        tp, fp, missed = match_findings(findings, [])
        assert tp == []
        assert len(fp) == 2
        assert missed == []

    def test_file_path_must_match_exactly(self) -> None:
        f = _finding(file_path="src/Auth.py")  # different case
        ann = _annotated(file_path="src/auth.py")
        tp, fp, missed = match_findings([f], [ann])
        assert tp == []
        assert fp == [f]
        assert missed == [ann]


# ---------------------------------------------------------------------------
# compute_metrics
# ---------------------------------------------------------------------------


class TestComputeMetrics:
    def _make_passing_result(self, pr_id: str = "repo_1") -> EvalResult:
        """A result that would contribute to passing all Appendix D targets."""
        f = _finding(category=Category.BUG)
        ann = _annotated()
        return _result(
            pr_id=pr_id,
            findings_produced=[f],
            expected_findings=[ann],
            true_positives=[f],
            false_positives=[],
            missed=[],
            latency_ms=15_000,  # 15s — under P50/P95 targets
        )

    def test_raises_on_empty_results(self) -> None:
        with pytest.raises(ValueError, match="empty results"):
            compute_metrics([])

    def test_basic_metrics_all_tp(self) -> None:
        results = [self._make_passing_result(f"pr_{i}") for i in range(5)]
        m = compute_metrics(results)
        assert m.pr_count == 5
        assert m.total_true_positives == 5
        assert m.total_false_positives == 0
        assert m.total_missed == 0
        assert m.accepted_finding_rate == 1.0

    def test_accepted_finding_rate_zero_when_all_fp(self) -> None:
        # No TPs, all produced are FPs → precision = 0/(0+FP) = 0.0
        f = _finding(file_path="src/other.py")
        r = _result(
            findings_produced=[f],
            expected_findings=[],
            true_positives=[],
            false_positives=[f],
            missed=[],
        )
        m = compute_metrics([r])
        assert m.accepted_finding_rate == 0.0

    def test_accepted_finding_rate_partial(self) -> None:
        # 1 TP, 1 FP → accepted_finding_rate = TP/(TP+FP) = 1/2 = 0.5
        tp_f = _finding()
        fp_f = _finding(file_path="src/other.py")
        ann = _annotated()
        r = _result(
            findings_produced=[tp_f, fp_f],
            expected_findings=[ann],
            true_positives=[tp_f],
            false_positives=[fp_f],
            missed=[],
        )
        m = compute_metrics([r])
        assert m.accepted_finding_rate == pytest.approx(0.5)

    def test_recall_partial(self) -> None:
        # 1 TP, 1 missed → recall = TP/(TP+missed) = 1/2 = 0.5
        f = _finding()
        ann1 = _annotated()
        ann2 = _annotated(line_range=(100, 100))
        r = _result(
            findings_produced=[f],
            expected_findings=[ann1, ann2],
            true_positives=[f],
            false_positives=[],
            missed=[ann2],
        )
        m = compute_metrics([r])
        assert m.recall == pytest.approx(0.5)

    def test_comments_per_pr_defects_only(self) -> None:
        # BUG (defect), SECURITY (defect), STYLE (not defect)
        findings = [
            _finding(category=Category.BUG),
            _finding(category=Category.SECURITY),
            _finding(category=Category.STYLE),
        ]
        r = _result(findings_produced=findings)
        m = compute_metrics([r])
        # Only 2 defect findings
        assert m.comments_per_pr_defects == 2.0

    def test_defect_categories_are_correct(self) -> None:
        assert Category.BUG in _DEFECT_CATEGORIES
        assert Category.SECURITY in _DEFECT_CATEGORIES
        assert Category.BREAKING_CHANGE in _DEFECT_CATEGORIES
        assert Category.STYLE not in _DEFECT_CATEGORIES
        assert Category.PERFORMANCE not in _DEFECT_CATEGORIES

    def test_fp_rate_verified(self) -> None:
        verified_fp = _finding(confidence=Confidence.VERIFIED)
        high_fp = _finding(confidence=Confidence.HIGH)
        tp = _finding()
        r = _result(
            findings_produced=[verified_fp, high_fp, tp],
            true_positives=[tp],
            false_positives=[verified_fp, high_fp],
        )
        m = compute_metrics([r])
        assert m.fp_rate_verified == pytest.approx(1 / 3)

    def test_fp_rate_high_confidence(self) -> None:
        verified_fp = _finding(confidence=Confidence.VERIFIED)
        high_fp = _finding(confidence=Confidence.HIGH)
        medium_fp = _finding(confidence=Confidence.MEDIUM)
        r = _result(
            findings_produced=[verified_fp, high_fp, medium_fp],
            false_positives=[verified_fp, high_fp, medium_fp],
        )
        m = compute_metrics([r])
        # verified + high = 2 out of 3
        assert m.fp_rate_high_confidence == pytest.approx(2 / 3)

    def test_latency_p50(self) -> None:
        latencies = [5_000, 10_000, 15_000, 20_000, 25_000]
        results = [_result(pr_id=f"pr_{i}", latency_ms=lat) for i, lat in enumerate(latencies)]
        m = compute_metrics(results)
        expected_p50 = statistics.median([ms / 1000.0 for ms in latencies])
        assert m.latency_p50_seconds == pytest.approx(expected_p50)

    def test_latency_p95(self) -> None:
        # 20 results, p95 should be the 19th (index 18 of sorted)
        latencies_ms = list(range(1_000, 21_000, 1_000))
        results = [_result(pr_id=f"pr_{i}", latency_ms=lat) for i, lat in enumerate(latencies_ms)]
        m = compute_metrics(results)
        # sorted: 1-20s, p95 index = int(20 * 0.95) = 19 → 20s
        assert m.latency_p95_seconds == pytest.approx(20.0)

    def test_cost_aggregation(self) -> None:
        r1 = _result(pr_id="pr_1", cost_usd=0.10, tokens_in=1000, tokens_out=200)
        r2 = _result(pr_id="pr_2", cost_usd=0.20, tokens_in=2000, tokens_out=400)
        m = compute_metrics([r1, r2])
        assert m.total_cost_usd == pytest.approx(0.30)
        assert m.avg_cost_per_pr_usd == pytest.approx(0.15)
        assert m.total_tokens_in == 3000
        assert m.total_tokens_out == 600

    def test_target_flags_all_passing(self) -> None:
        # Craft results that hit all Appendix D targets
        findings = [_finding(category=Category.BUG)]  # 1 defect finding < 8
        ann = _annotated()
        r = _result(
            findings_produced=findings,
            expected_findings=[ann],
            true_positives=findings,
            false_positives=[],
            missed=[],
            latency_ms=10_000,  # 10s
        )
        m = compute_metrics([r])
        assert m.meets_comments_per_pr_target  # 1 < 8
        assert m.meets_accepted_finding_target  # 1.0 > 0.60
        assert m.meets_fp_verified_target  # 0 < 0.01
        assert m.meets_fp_high_confidence_target  # 0 < 0.10
        assert m.meets_latency_p50_target  # 10s < 30s
        assert m.meets_latency_p95_target  # 10s < 60s
        assert m.all_targets_met

    def test_target_flags_failing(self) -> None:
        # Lots of FPs, slow, high comment count
        fps = [
            _finding(confidence=Confidence.VERIFIED, category=Category.BUG),
        ] * 50
        r = _result(
            findings_produced=fps,
            false_positives=fps,
            latency_ms=70_000,  # 70s — exceeds P95 target
        )
        m = compute_metrics([r])
        # 50 defects >> 8
        assert not m.meets_comments_per_pr_target
        # no TPs at all
        assert not m.meets_accepted_finding_target
        # verified FPs / total > 1%
        assert not m.meets_fp_verified_target
        # 70s > 60s P95
        assert not m.meets_latency_p95_target
        assert not m.all_targets_met

    def test_variant_preserved(self) -> None:
        r = _result(variant="diff_only")
        m = compute_metrics([r])
        assert m.variant == "diff_only"

    def test_zero_findings_produced_zero_fp_rates(self) -> None:
        # No findings produced — FP rates should be 0.0, not a division error
        ann = _annotated()
        r = _result(
            findings_produced=[],
            expected_findings=[ann],
            missed=[ann],
        )
        m = compute_metrics([r])
        assert m.fp_rate_verified == 0.0
        assert m.fp_rate_high_confidence == 0.0

    def test_no_findings_zero_denominator_for_accepted_rate(self) -> None:
        # No findings produced (TP=0, FP=0) — accepted_finding_rate should be 0 not divide-by-zero
        r = _result(findings_produced=[], expected_findings=[], missed=[])
        m = compute_metrics([r])
        assert m.accepted_finding_rate == 0.0
        assert m.recall == 0.0


# ---------------------------------------------------------------------------
# write_report
# ---------------------------------------------------------------------------


class TestWriteReport:
    def _make_metrics(self, variant: str = "structural") -> tuple[EvalMetrics, list[EvalResult]]:
        f = _finding(category=Category.BUG)
        ann = _annotated()
        r = _result(
            pr_id="myrepo_1",
            variant=variant,
            findings_produced=[f],
            expected_findings=[ann],
            true_positives=[f],
            false_positives=[],
            missed=[],
            latency_ms=12_000,
            tokens_in=500,
            tokens_out=100,
            cost_usd=0.005,
        )
        m = compute_metrics([r])
        return m, [r]

    def test_creates_json_and_markdown(self, tmp_path: Path) -> None:
        m, results = self._make_metrics()
        json_path, md_path = write_report(m, results, output_dir=tmp_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_json_structure(self, tmp_path: Path) -> None:
        m, results = self._make_metrics()
        json_path, _ = write_report(m, results, output_dir=tmp_path)
        data = json.loads(json_path.read_text())
        assert data["variant"] == "structural"
        assert data["pr_count"] == 1
        assert "metrics" in data
        assert "targets" in data
        assert "totals" in data
        assert "per_pr" in data

    def test_json_metrics_keys(self, tmp_path: Path) -> None:
        m, results = self._make_metrics()
        json_path, _ = write_report(m, results, output_dir=tmp_path)
        data = json.loads(json_path.read_text())
        keys = set(data["metrics"].keys())
        assert keys == {
            "comments_per_pr_defects",
            "accepted_finding_rate",
            "fp_rate_verified",
            "fp_rate_high_confidence",
            "latency_p50_seconds",
            "latency_p95_seconds",
        }

    def test_json_all_targets_met_field(self, tmp_path: Path) -> None:
        m, results = self._make_metrics()
        json_path, _ = write_report(m, results, output_dir=tmp_path)
        data = json.loads(json_path.read_text())
        assert "all_met" in data["targets"]

    def test_json_per_pr_row(self, tmp_path: Path) -> None:
        m, results = self._make_metrics()
        json_path, _ = write_report(m, results, output_dir=tmp_path)
        data = json.loads(json_path.read_text())
        row = data["per_pr"][0]
        assert row["pr_id"] == "myrepo_1"
        assert row["findings_produced"] == 1
        assert row["true_positives"] == 1
        assert row["latency_ms"] == 12_000

    def test_markdown_contains_variant(self, tmp_path: Path) -> None:
        m, results = self._make_metrics()
        _, md_path = write_report(m, results, output_dir=tmp_path)
        text = md_path.read_text()
        assert "structural" in text

    def test_markdown_contains_table_headers(self, tmp_path: Path) -> None:
        m, results = self._make_metrics()
        _, md_path = write_report(m, results, output_dir=tmp_path)
        text = md_path.read_text()
        assert "Accepted-finding rate" in text
        assert "FP rate" in text
        assert "Latency P50" in text

    def test_markdown_contains_pr_row(self, tmp_path: Path) -> None:
        m, results = self._make_metrics()
        _, md_path = write_report(m, results, output_dir=tmp_path)
        text = md_path.read_text()
        assert "myrepo_1" in text

    def test_diff_only_variant_in_filename(self, tmp_path: Path) -> None:
        m, results = self._make_metrics(variant="diff_only")
        json_path, md_path = write_report(m, results, output_dir=tmp_path)
        assert "diff_only" in json_path.name
        assert "diff_only" in md_path.name

    def test_output_dir_created_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "dir"
        m, results = self._make_metrics()
        write_report(m, results, output_dir=nested)
        assert nested.exists()
