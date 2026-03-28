"""Unit tests for the Bet A comparison report (DEM-154 — diff-only baseline).

Covers:
- compare_variants: lift computation, Bet A go/no-go thresholds
- Graph-origin fraction calculation
- write_comparison_report: JSON and markdown output
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from kenjutsu.evaluation.runner import (
    AnnotatedFinding,
    ComparisonReport,
    EvalMetrics,
    EvalResult,
    compare_variants,
    write_comparison_report,
)
from kenjutsu.models import Category, Confidence, Finding, Origin, Publishability, Severity

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metrics(
    variant: str = "structural",
    accepted_finding_rate: float = 0.65,
    fp_rate_high_confidence: float = 0.08,
    comments_per_pr_defects: float = 6.0,
    latency_p50_seconds: float = 20.0,
    latency_p95_seconds: float = 45.0,
    pr_count: int = 5,
) -> EvalMetrics:
    return EvalMetrics(
        variant=variant,
        pr_count=pr_count,
        total_findings_produced=50,
        total_true_positives=30,
        total_false_positives=5,
        total_missed=10,
        comments_per_pr_defects=comments_per_pr_defects,
        accepted_finding_rate=accepted_finding_rate,
        fp_rate_verified=0.005,
        fp_rate_high_confidence=fp_rate_high_confidence,
        latency_p50_seconds=latency_p50_seconds,
        latency_p95_seconds=latency_p95_seconds,
        total_tokens_in=5000,
        total_tokens_out=1000,
        total_cost_usd=0.05,
        avg_cost_per_pr_usd=0.01,
        meets_comments_per_pr_target=True,
        meets_accepted_finding_target=True,
        meets_fp_verified_target=True,
        meets_fp_high_confidence_target=True,
        meets_latency_p50_target=True,
        meets_latency_p95_target=True,
    )


def _finding(origin: Origin = Origin.GRAPH) -> Finding:
    return Finding(
        file_path="src/auth.py",
        line_start=42,
        line_end=42,
        origin=origin,
        confidence=Confidence.HIGH,
        severity=Severity.WARNING,
        category=Category.BUG,
        publishability=Publishability.PUBLISH,
        description="test finding",
    )


def _annotated() -> AnnotatedFinding:
    return AnnotatedFinding(
        file_path="src/auth.py",
        line_range=(42, 42),
        category=Category.BUG,
        severity=Severity.WARNING,
        confidence=Confidence.VERIFIED,
        description="test expected finding",
    )


def _result_with_tps(tp_findings: list[Finding], pr_id: str = "repo_1") -> EvalResult:
    return EvalResult(
        pr_id=pr_id,
        variant="structural",
        findings_produced=tp_findings,
        expected_findings=[_annotated() for _ in tp_findings],
        true_positives=tp_findings,
        false_positives=[],
        missed=[],
        latency_ms=10_000,
        tokens_in=500,
        tokens_out=100,
        cost_usd=0.01,
    )


# ---------------------------------------------------------------------------
# compare_variants — lift computation
# ---------------------------------------------------------------------------


class TestCompareVariants:
    def test_accepted_finding_lift_positive(self) -> None:
        structural = _metrics(variant="structural", accepted_finding_rate=0.65)
        diff_only = _metrics(variant="diff_only", accepted_finding_rate=0.45)
        report = compare_variants(structural, diff_only)
        assert report.accepted_finding_lift == pytest.approx(0.20)

    def test_accepted_finding_lift_negative(self) -> None:
        # Pathological case: structural is worse
        structural = _metrics(variant="structural", accepted_finding_rate=0.40)
        diff_only = _metrics(variant="diff_only", accepted_finding_rate=0.50)
        report = compare_variants(structural, diff_only)
        assert report.accepted_finding_lift == pytest.approx(-0.10)

    def test_fp_lift_positive_when_structural_better(self) -> None:
        structural = _metrics(variant="structural", fp_rate_high_confidence=0.05)
        diff_only = _metrics(variant="diff_only", fp_rate_high_confidence=0.18)
        report = compare_variants(structural, diff_only)
        fp_comp = next(c for c in report.comparisons if "FP rate" in c.metric)
        assert fp_comp.lift == pytest.approx(0.13)

    def test_comparison_contains_all_required_metrics(self) -> None:
        structural = _metrics()
        diff_only = _metrics(variant="diff_only")
        report = compare_variants(structural, diff_only)
        metric_names = {c.metric for c in report.comparisons}
        assert "Accepted-finding rate" in metric_names
        assert "FP rate (high confidence)" in metric_names
        assert "Comments per PR" in metric_names
        assert "Latency P50" in metric_names
        assert "Latency P95" in metric_names

    def test_comments_per_pr_lift_positive_when_structural_fewer(self) -> None:
        structural = _metrics(comments_per_pr_defects=5.0)
        diff_only = _metrics(variant="diff_only", comments_per_pr_defects=10.0)
        report = compare_variants(structural, diff_only)
        comments_comp = next(c for c in report.comparisons if "Comments" in c.metric)
        assert comments_comp.lift == pytest.approx(5.0)

    def test_latency_lift_positive_when_structural_slower(self) -> None:
        structural = _metrics(latency_p50_seconds=25.0)
        diff_only = _metrics(variant="diff_only", latency_p50_seconds=10.0)
        report = compare_variants(structural, diff_only)
        p50_comp = next(c for c in report.comparisons if "P50" in c.metric)
        # diff_only is faster — lift is diff_only - structural (negative for user)
        assert p50_comp.lift == pytest.approx(-15.0)


# ---------------------------------------------------------------------------
# Bet A go/no-go
# ---------------------------------------------------------------------------


class TestBetAGoNoGo:
    def test_go_when_both_thresholds_met(self) -> None:
        structural = _metrics(accepted_finding_rate=0.65)  # diff_only=0.45 → lift=0.20 > 0.15
        diff_only = _metrics(variant="diff_only", accepted_finding_rate=0.45)
        graph_tp = _finding(origin=Origin.GRAPH)
        other_tp = _finding(origin=Origin.LLM)
        # 3 graph TPs out of 5 total = 60% > 20%
        results = [
            _result_with_tps([graph_tp, graph_tp, graph_tp, other_tp, other_tp], pr_id="pr_1"),
        ]
        report = compare_variants(structural, diff_only, structural_results=results)
        assert report.bet_a_go is True

    def test_no_go_when_lift_below_threshold(self) -> None:
        structural = _metrics(accepted_finding_rate=0.55)  # lift = 0.10 < 0.15
        diff_only = _metrics(variant="diff_only", accepted_finding_rate=0.45)
        graph_tp = _finding(origin=Origin.GRAPH)
        results = [_result_with_tps([graph_tp, graph_tp, graph_tp], pr_id="pr_1")]
        report = compare_variants(structural, diff_only, structural_results=results)
        assert report.bet_a_go is False
        assert "≤" in report.bet_a_reason

    def test_no_go_when_graph_fraction_below_threshold(self) -> None:
        structural = _metrics(accepted_finding_rate=0.65)  # lift = 0.20 ✅
        diff_only = _metrics(variant="diff_only", accepted_finding_rate=0.45)
        llm_tp = _finding(origin=Origin.LLM)
        # Only LLM findings — 0% graph origin < 20%
        results = [_result_with_tps([llm_tp, llm_tp, llm_tp], pr_id="pr_1")]
        report = compare_variants(structural, diff_only, structural_results=results)
        assert report.bet_a_go is False

    def test_no_go_when_no_structural_results_passed(self) -> None:
        structural = _metrics(accepted_finding_rate=0.65)
        diff_only = _metrics(variant="diff_only", accepted_finding_rate=0.45)
        # No structural_results — graph_origin_fraction defaults to 0.0
        report = compare_variants(structural, diff_only)
        assert report.graph_origin_fraction == 0.0
        assert report.bet_a_go is False  # 0% < 20% threshold

    def test_graph_origin_fraction_correct(self) -> None:
        structural = _metrics()
        diff_only = _metrics(variant="diff_only")
        graph_tp = _finding(origin=Origin.GRAPH)
        llm_tp = _finding(origin=Origin.LLM)
        # 1 graph out of 4 total = 25%
        results = [_result_with_tps([graph_tp, llm_tp, llm_tp, llm_tp], pr_id="pr_1")]
        report = compare_variants(structural, diff_only, structural_results=results)
        assert report.graph_origin_fraction == pytest.approx(0.25)

    def test_graph_fraction_zero_when_no_tps(self) -> None:
        structural = _metrics()
        diff_only = _metrics(variant="diff_only")
        # No TPs in results
        r = EvalResult(
            pr_id="pr_1",
            variant="structural",
            findings_produced=[],
            expected_findings=[],
            true_positives=[],
            false_positives=[],
            missed=[],
            latency_ms=1000,
            tokens_in=100,
            tokens_out=10,
            cost_usd=0.001,
        )
        report = compare_variants(structural, diff_only, structural_results=[r])
        assert report.graph_origin_fraction == 0.0

    def test_reason_mentions_both_criteria(self) -> None:
        structural = _metrics()
        diff_only = _metrics(variant="diff_only")
        report = compare_variants(structural, diff_only)
        assert "accepted-finding lift" in report.bet_a_reason
        assert "graph-origin fraction" in report.bet_a_reason


# ---------------------------------------------------------------------------
# write_comparison_report
# ---------------------------------------------------------------------------


class TestWriteComparisonReport:
    def _make_report(self) -> tuple[ComparisonReport, EvalMetrics, EvalMetrics]:
        structural = _metrics(variant="structural", accepted_finding_rate=0.65)
        diff_only = _metrics(variant="diff_only", accepted_finding_rate=0.45)
        report = compare_variants(structural, diff_only)
        return report, structural, diff_only

    def test_creates_json_and_markdown(self, tmp_path: Path) -> None:
        report, structural, diff_only = self._make_report()
        json_path, md_path = write_comparison_report(report, structural, diff_only, tmp_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_json_has_bet_a_block(self, tmp_path: Path) -> None:
        report, structural, diff_only = self._make_report()
        json_path, _ = write_comparison_report(report, structural, diff_only, tmp_path)
        data = json.loads(json_path.read_text())
        assert "bet_a" in data
        assert "go" in data["bet_a"]
        assert "accepted_finding_lift" in data["bet_a"]
        assert "graph_origin_fraction" in data["bet_a"]

    def test_json_has_metrics_array(self, tmp_path: Path) -> None:
        report, structural, diff_only = self._make_report()
        json_path, _ = write_comparison_report(report, structural, diff_only, tmp_path)
        data = json.loads(json_path.read_text())
        assert "metrics" in data
        assert len(data["metrics"]) == 5

    def test_json_metric_row_structure(self, tmp_path: Path) -> None:
        report, structural, diff_only = self._make_report()
        json_path, _ = write_comparison_report(report, structural, diff_only, tmp_path)
        data = json.loads(json_path.read_text())
        row = data["metrics"][0]
        assert "metric" in row
        assert "diff_only" in row
        assert "structural" in row
        assert "lift" in row

    def test_json_accepted_finding_lift_value(self, tmp_path: Path) -> None:
        report, structural, diff_only = self._make_report()
        json_path, _ = write_comparison_report(report, structural, diff_only, tmp_path)
        data = json.loads(json_path.read_text())
        assert data["bet_a"]["accepted_finding_lift"] == pytest.approx(0.20, abs=0.001)

    def test_markdown_contains_verdict(self, tmp_path: Path) -> None:
        report, structural, diff_only = self._make_report()
        _, md_path = write_comparison_report(report, structural, diff_only, tmp_path)
        text = md_path.read_text()
        assert "Verdict" in text

    def test_markdown_contains_metric_table(self, tmp_path: Path) -> None:
        report, structural, diff_only = self._make_report()
        _, md_path = write_comparison_report(report, structural, diff_only, tmp_path)
        text = md_path.read_text()
        assert "Accepted-finding rate" in text
        assert "FP rate" in text
        assert "Latency P50" in text

    def test_markdown_go_shows_checkmark(self, tmp_path: Path) -> None:
        structural = _metrics(variant="structural", accepted_finding_rate=0.65)
        diff_only = _metrics(variant="diff_only", accepted_finding_rate=0.45)
        # Force graph origin > threshold
        graph_tp = _finding(origin=Origin.GRAPH)
        llm_tp = _finding(origin=Origin.LLM)
        results = [_result_with_tps([graph_tp, graph_tp, graph_tp, llm_tp], pr_id="pr_1")]
        report = compare_variants(structural, diff_only, structural_results=results)
        _, md_path = write_comparison_report(report, structural, diff_only, tmp_path)
        text = md_path.read_text()
        assert "GO ✅" in text

    def test_markdown_no_go_shows_cross(self, tmp_path: Path) -> None:
        # lift < threshold
        structural = _metrics(variant="structural", accepted_finding_rate=0.50)
        diff_only = _metrics(variant="diff_only", accepted_finding_rate=0.45)
        report = compare_variants(structural, diff_only)
        _, md_path = write_comparison_report(report, structural, diff_only, tmp_path)
        text = md_path.read_text()
        assert "NO-GO ❌" in text

    def test_output_dir_created_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "comparison"
        report, structural, diff_only = self._make_report()
        write_comparison_report(report, structural, diff_only, nested)
        assert nested.exists()

    def test_filename_contains_comparison_stem(self, tmp_path: Path) -> None:
        report, structural, diff_only = self._make_report()
        json_path, md_path = write_comparison_report(report, structural, diff_only, tmp_path)
        assert "comparison" in json_path.name
        assert "comparison" in md_path.name
