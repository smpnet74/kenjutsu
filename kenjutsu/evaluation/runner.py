"""Evaluation runner — measures Kenjutsu review quality against a benchmark corpus.

Architecture plan: DEM-138 (1.9 Evaluation Harness)
Spec refs: v3 Appendix D (metrics targets), Appendix E (evaluation contract)

Usage:
    pipeline = MyReviewPipeline()
    corpus = load_corpus("evaluation/corpus")
    results = await run_eval(corpus, pipeline, variant="structural")
    metrics = compute_metrics(results)
    write_report(metrics, results, output_dir="evaluation/results")
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from kenjutsu.models import Category, Confidence, Finding, Severity

# ---------------------------------------------------------------------------
# Corpus / annotation types
# ---------------------------------------------------------------------------


@dataclass
class AnnotatedFinding:
    """Ground-truth finding from the benchmark corpus.

    Produced by human annotators. The evaluation runner matches pipeline
    output against these to classify TPs, FPs, and misses.
    """

    file_path: str
    line_range: tuple[int, int]  # (start, end) inclusive
    category: Category
    severity: Severity
    confidence: Confidence
    description: str


@dataclass
class BenchmarkPR:
    """One annotated PR from the corpus."""

    pr_id: str  # canonical "{repo}_{pr_number}" identifier
    repo: str
    pr_number: int
    head_sha: str
    base_sha: str
    languages: list[str]
    size: str  # "small" | "medium" | "large"
    tags: list[str]
    expected_findings: list[AnnotatedFinding]
    false_positive_patterns: list[dict[str, str]]  # descriptive, not matched


@dataclass
class Corpus:
    """The full benchmark corpus — a collection of annotated PRs."""

    prs: list[BenchmarkPR]

    def __len__(self) -> int:
        return len(self.prs)


# ---------------------------------------------------------------------------
# Pipeline adapter protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ReviewPipeline(Protocol):
    """Minimal interface the evaluation runner requires from the review pipeline.

    The real pipeline (not yet built) will implement this.  Tests and local
    runs can substitute a mock that conforms to the same protocol.
    """

    async def review(
        self,
        repo: str,
        pr_number: int,
        head_sha: str,
        base_sha: str,
        *,
        variant: str = "structural",
    ) -> tuple[list[Finding], dict[str, int | float]]:
        """Run the review pipeline for a single PR.

        Returns:
            findings: list of Finding objects produced by the pipeline
            telemetry: dict with keys latency_ms, tokens_in, tokens_out, cost_usd
        """
        ...


# ---------------------------------------------------------------------------
# Evaluation result types
# ---------------------------------------------------------------------------


@dataclass
class EvalResult:
    """Per-PR evaluation result with TP/FP/miss breakdown."""

    pr_id: str
    variant: str
    findings_produced: list[Finding]
    expected_findings: list[AnnotatedFinding]
    true_positives: list[Finding]  # produced AND matches an expected finding
    false_positives: list[Finding]  # produced but no expected match
    missed: list[AnnotatedFinding]  # expected but no produced match
    latency_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float


@dataclass
class EvalMetrics:
    """Aggregated evaluation metrics across all PRs (Appendix D targets).

    Targets:
        comments_per_pr_defects:    < 8    (defect-only findings)
        accepted_finding_rate:      > 0.60 (TP / (TP + missed))
        fp_rate_verified:           < 0.01 (verified-confidence FPs / total findings)
        fp_rate_high_confidence:    < 0.10 (high-or-better confidence FPs / total findings)
        latency_p50_seconds:        < 30s
        latency_p95_seconds:        < 60s
    """

    variant: str
    pr_count: int
    total_findings_produced: int
    total_true_positives: int
    total_false_positives: int
    total_missed: int

    # Appendix D metrics
    comments_per_pr_defects: float  # average defect findings per PR
    accepted_finding_rate: float  # TP / (TP + missed); 0-1
    fp_rate_verified: float  # verified-confidence FPs / total produced
    fp_rate_high_confidence: float  # high+ confidence FPs / total produced
    latency_p50_seconds: float
    latency_p95_seconds: float

    # Additional cost/token telemetry
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float
    avg_cost_per_pr_usd: float

    # Target flags (pass/fail vs Appendix D)
    meets_comments_per_pr_target: bool  # < 8
    meets_accepted_finding_target: bool  # > 0.60
    meets_fp_verified_target: bool  # < 0.01
    meets_fp_high_confidence_target: bool  # < 0.10
    meets_latency_p50_target: bool  # < 30s
    meets_latency_p95_target: bool  # < 60s

    @property
    def all_targets_met(self) -> bool:
        return all(
            [
                self.meets_comments_per_pr_target,
                self.meets_accepted_finding_target,
                self.meets_fp_verified_target,
                self.meets_fp_high_confidence_target,
                self.meets_latency_p50_target,
                self.meets_latency_p95_target,
            ]
        )


# ---------------------------------------------------------------------------
# Finding matching
# ---------------------------------------------------------------------------

_DEFECT_CATEGORIES = {Category.BUG, Category.SECURITY, Category.BREAKING_CHANGE}


def _line_ranges_overlap(
    produced: tuple[int, int],
    expected: tuple[int, int],
    *,
    tolerance: int = 5,
) -> bool:
    """True when produced and expected line ranges overlap with a tolerance window.

    The tolerance handles minor line-number drift between the diff the pipeline
    saw and the line numbers in the ground-truth annotation.
    """
    p_start, p_end = produced
    e_start, e_end = expected
    # Expand expected range by tolerance
    e_start_adj = e_start - tolerance
    e_end_adj = e_end + tolerance
    return p_start <= e_end_adj and p_end >= e_start_adj


def match_findings(
    produced: list[Finding],
    expected: list[AnnotatedFinding],
) -> tuple[list[Finding], list[Finding], list[AnnotatedFinding]]:
    """Classify produced findings against expected ground truth.

    Matching rule: a produced finding matches an expected finding when:
        1. file_path is identical
        2. category is identical
        3. line ranges overlap (with tolerance)

    Each expected finding can be matched at most once (first match wins).

    Returns:
        true_positives:  produced findings that matched an expected finding
        false_positives: produced findings that matched no expected finding
        missed:          expected findings that no produced finding matched
    """
    unmatched_expected = list(expected)
    true_positives: list[Finding] = []
    false_positives: list[Finding] = []

    for finding in produced:
        matched = False
        for i, ann in enumerate(unmatched_expected):
            if (
                finding.file_path == ann.file_path
                and finding.category == ann.category
                and _line_ranges_overlap(
                    (finding.line_start, finding.line_end),
                    ann.line_range,
                )
            ):
                true_positives.append(finding)
                unmatched_expected.pop(i)
                matched = True
                break
        if not matched:
            false_positives.append(finding)

    return true_positives, false_positives, unmatched_expected


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------


def compute_metrics(results: list[EvalResult]) -> EvalMetrics:
    """Aggregate per-PR EvalResults into EvalMetrics (Appendix D targets).

    Raises ValueError if results is empty.
    """
    if not results:
        msg = "Cannot compute metrics from empty results list"
        raise ValueError(msg)

    variant = results[0].variant
    pr_count = len(results)

    total_findings_produced = sum(len(r.findings_produced) for r in results)
    total_true_positives = sum(len(r.true_positives) for r in results)
    total_false_positives = sum(len(r.false_positives) for r in results)
    total_missed = sum(len(r.missed) for r in results)

    # Comments per PR — defect-severity findings only
    defect_counts = [sum(1 for f in r.findings_produced if f.category in _DEFECT_CATEGORIES) for r in results]
    comments_per_pr_defects = statistics.mean(defect_counts)

    # Accepted-finding rate: TP / (TP + missed)
    denominator = total_true_positives + total_missed
    accepted_finding_rate = total_true_positives / denominator if denominator > 0 else 0.0

    # FP rates
    fp_verified = [f for r in results for f in r.false_positives if f.confidence == Confidence.VERIFIED]
    fp_high_or_better = [
        f for r in results for f in r.false_positives if f.confidence in {Confidence.VERIFIED, Confidence.HIGH}
    ]
    fp_rate_verified = len(fp_verified) / total_findings_produced if total_findings_produced > 0 else 0.0
    fp_rate_high_confidence = len(fp_high_or_better) / total_findings_produced if total_findings_produced > 0 else 0.0

    # Latency percentiles
    latencies_s = [r.latency_ms / 1000.0 for r in results]
    latency_p50 = statistics.median(latencies_s)
    latencies_sorted = sorted(latencies_s)
    p95_index = int(len(latencies_sorted) * 0.95)
    latency_p95 = latencies_sorted[min(p95_index, len(latencies_sorted) - 1)]

    # Cost / token totals
    total_tokens_in = sum(r.tokens_in for r in results)
    total_tokens_out = sum(r.tokens_out for r in results)
    total_cost_usd = sum(r.cost_usd for r in results)
    avg_cost_per_pr_usd = total_cost_usd / pr_count

    return EvalMetrics(
        variant=variant,
        pr_count=pr_count,
        total_findings_produced=total_findings_produced,
        total_true_positives=total_true_positives,
        total_false_positives=total_false_positives,
        total_missed=total_missed,
        comments_per_pr_defects=comments_per_pr_defects,
        accepted_finding_rate=accepted_finding_rate,
        fp_rate_verified=fp_rate_verified,
        fp_rate_high_confidence=fp_rate_high_confidence,
        latency_p50_seconds=latency_p50,
        latency_p95_seconds=latency_p95,
        total_tokens_in=total_tokens_in,
        total_tokens_out=total_tokens_out,
        total_cost_usd=total_cost_usd,
        avg_cost_per_pr_usd=avg_cost_per_pr_usd,
        meets_comments_per_pr_target=comments_per_pr_defects < 8,
        meets_accepted_finding_target=accepted_finding_rate > 0.60,
        meets_fp_verified_target=fp_rate_verified < 0.01,
        meets_fp_high_confidence_target=fp_rate_high_confidence < 0.10,
        meets_latency_p50_target=latency_p50 < 30.0,
        meets_latency_p95_target=latency_p95 < 60.0,
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run_eval(
    corpus: Corpus,
    pipeline: ReviewPipeline,
    *,
    variant: str = "structural",
) -> list[EvalResult]:
    """Run the review pipeline against every PR in the corpus.

    Args:
        corpus:  benchmark corpus (annotated PRs)
        pipeline: review pipeline adapter (see ReviewPipeline protocol)
        variant: "structural" (full pipeline) or "diff_only" (no structural context)

    Returns:
        list of EvalResult, one per PR, in corpus order
    """
    results: list[EvalResult] = []
    for pr in corpus.prs:
        t0 = time.monotonic()
        findings, telemetry = await pipeline.review(
            pr.repo,
            pr.pr_number,
            pr.head_sha,
            pr.base_sha,
            variant=variant,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        latency_ms = int(telemetry.get("latency_ms", elapsed_ms))
        tokens_in = int(telemetry.get("tokens_in", 0))
        tokens_out = int(telemetry.get("tokens_out", 0))
        cost_usd = float(telemetry.get("cost_usd", 0.0))

        tp, fp, missed = match_findings(findings, pr.expected_findings)

        results.append(
            EvalResult(
                pr_id=pr.pr_id,
                variant=variant,
                findings_produced=findings,
                expected_findings=pr.expected_findings,
                true_positives=tp,
                false_positives=fp,
                missed=missed,
                latency_ms=latency_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def write_report(
    metrics: EvalMetrics,
    results: list[EvalResult],
    output_dir: str | Path = "evaluation/results",
) -> tuple[Path, Path]:
    """Write JSON metrics file + markdown summary report.

    Returns:
        (json_path, markdown_path) — paths to the written files
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    stem = f"eval_{metrics.variant}_{timestamp}"

    json_path = output_path / f"{stem}.json"
    md_path = output_path / f"{stem}.md"

    # --- JSON ---
    payload = {
        "variant": metrics.variant,
        "generated_at": timestamp,
        "pr_count": metrics.pr_count,
        "metrics": {
            "comments_per_pr_defects": round(metrics.comments_per_pr_defects, 2),
            "accepted_finding_rate": round(metrics.accepted_finding_rate, 4),
            "fp_rate_verified": round(metrics.fp_rate_verified, 4),
            "fp_rate_high_confidence": round(metrics.fp_rate_high_confidence, 4),
            "latency_p50_seconds": round(metrics.latency_p50_seconds, 2),
            "latency_p95_seconds": round(metrics.latency_p95_seconds, 2),
        },
        "targets": {
            "comments_per_pr_defects": metrics.meets_comments_per_pr_target,
            "accepted_finding_rate": metrics.meets_accepted_finding_target,
            "fp_rate_verified": metrics.meets_fp_verified_target,
            "fp_rate_high_confidence": metrics.meets_fp_high_confidence_target,
            "latency_p50": metrics.meets_latency_p50_target,
            "latency_p95": metrics.meets_latency_p95_target,
            "all_met": metrics.all_targets_met,
        },
        "totals": {
            "findings_produced": metrics.total_findings_produced,
            "true_positives": metrics.total_true_positives,
            "false_positives": metrics.total_false_positives,
            "missed": metrics.total_missed,
            "tokens_in": metrics.total_tokens_in,
            "tokens_out": metrics.total_tokens_out,
            "cost_usd": round(metrics.total_cost_usd, 6),
            "avg_cost_per_pr_usd": round(metrics.avg_cost_per_pr_usd, 6),
        },
        "per_pr": [
            {
                "pr_id": r.pr_id,
                "findings_produced": len(r.findings_produced),
                "true_positives": len(r.true_positives),
                "false_positives": len(r.false_positives),
                "missed": len(r.missed),
                "latency_ms": r.latency_ms,
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "cost_usd": round(r.cost_usd, 6),
            }
            for r in results
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2))

    # --- Markdown ---
    def _check(passed: bool) -> str:
        return "✅" if passed else "❌"

    lines = [
        f"# Kenjutsu Evaluation Report — `{metrics.variant}`",
        "",
        f"Generated: {timestamp}  |  PRs evaluated: {metrics.pr_count}",
        "",
        "## Appendix D Metrics",
        "",
        "| Metric | Value | Target | Status |",
        "|--------|-------|--------|--------|",
        (
            f"| Comments/PR (defects) | {metrics.comments_per_pr_defects:.1f}"
            f" | < 8 | {_check(metrics.meets_comments_per_pr_target)} |"
        ),
        (
            f"| Accepted-finding rate | {metrics.accepted_finding_rate:.1%}"
            f" | > 60% | {_check(metrics.meets_accepted_finding_target)} |"
        ),
        (
            f"| FP rate (verified) | {metrics.fp_rate_verified:.2%}"
            f" | < 1% | {_check(metrics.meets_fp_verified_target)} |"
        ),
        (
            f"| FP rate (high confidence) | {metrics.fp_rate_high_confidence:.2%}"
            f" | < 10% | {_check(metrics.meets_fp_high_confidence_target)} |"
        ),
        f"| Latency P50 | {metrics.latency_p50_seconds:.1f}s | < 30s | {_check(metrics.meets_latency_p50_target)} |",
        f"| Latency P95 | {metrics.latency_p95_seconds:.1f}s | < 60s | {_check(metrics.meets_latency_p95_target)} |",
        "",
        f"**Overall:** {'All targets met ✅' if metrics.all_targets_met else 'Some targets missed ❌'}",
        "",
        "## Finding Totals",
        "",
        "| | Count |",
        "|--|-------|",
        f"| Total produced | {metrics.total_findings_produced} |",
        f"| True positives | {metrics.total_true_positives} |",
        f"| False positives | {metrics.total_false_positives} |",
        f"| Missed | {metrics.total_missed} |",
        "",
        "## Cost & Tokens",
        "",
        "| | Value |",
        "|--|-------|",
        f"| Tokens in | {metrics.total_tokens_in:,} |",
        f"| Tokens out | {metrics.total_tokens_out:,} |",
        f"| Total cost | ${metrics.total_cost_usd:.4f} |",
        f"| Avg cost/PR | ${metrics.avg_cost_per_pr_usd:.4f} |",
        "",
        "## Per-PR Results",
        "",
        "| PR | Produced | TP | FP | Missed | Latency |",
        "|----|----------|----|----|--------|---------|",
    ]
    for r in results:
        lines.append(
            f"| {r.pr_id} | {len(r.findings_produced)} | {len(r.true_positives)} "
            f"| {len(r.false_positives)} | {len(r.missed)} | {r.latency_ms}ms |"
        )

    md_path.write_text("\n".join(lines) + "\n")

    return json_path, md_path
