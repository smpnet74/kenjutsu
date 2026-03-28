"""Evaluation harness — measures Kenjutsu review quality against a benchmark corpus."""

from kenjutsu.evaluation.runner import (
    AnnotatedFinding,
    ComparisonReport,
    Corpus,
    EvalMetrics,
    EvalResult,
    MetricComparison,
    ReviewPipeline,
    compare_variants,
    compute_metrics,
    run_eval,
    write_comparison_report,
)

__all__ = [
    "AnnotatedFinding",
    "ComparisonReport",
    "Corpus",
    "EvalMetrics",
    "EvalResult",
    "MetricComparison",
    "ReviewPipeline",
    "compare_variants",
    "compute_metrics",
    "run_eval",
    "write_comparison_report",
]
