"""Integration test for the evaluation runner.

Runs a small 5-PR corpus end-to-end through a mock pipeline and verifies:
- Correct TP/FP/miss counts across all PRs
- Metrics output format (JSON + markdown produced)
- Variant parameter is passed through to the pipeline
- run_eval + compute_metrics + write_report compose correctly
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kenjutsu.evaluation.runner import (
    AnnotatedFinding,
    BenchmarkPR,
    Corpus,
    EvalResult,
    compute_metrics,
    run_eval,
    write_report,
)
from kenjutsu.models import Category, Confidence, Finding, Origin, Publishability, Severity

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Mock pipeline
# ---------------------------------------------------------------------------


class MockPipeline:
    """Deterministic mock that returns a fixed finding list per PR.

    per_pr_findings: maps pr_id -> list of findings the pipeline produces
    captured_variants: records which variant was requested for each call
    """

    def __init__(self, per_pr_findings: dict[str, list[Finding]]) -> None:
        self._per_pr_findings = per_pr_findings
        self.captured_variants: list[str] = []

    async def review(
        self,
        repo: str,
        pr_number: int,
        head_sha: str,
        base_sha: str,
        *,
        variant: str = "structural",
    ) -> tuple[list[Finding], dict[str, int | float]]:
        self.captured_variants.append(variant)
        pr_id = f"{repo.replace('/', '_')}_{pr_number}"
        findings = self._per_pr_findings.get(pr_id, [])
        telemetry: dict[str, int | float] = {
            "latency_ms": 8_000,
            "tokens_in": 500,
            "tokens_out": 100,
            "cost_usd": 0.005,
        }
        return findings, telemetry


def _f(
    file_path: str,
    line_start: int,
    category: Category = Category.BUG,
    confidence: Confidence = Confidence.HIGH,
) -> Finding:
    return Finding(
        file_path=file_path,
        line_start=line_start,
        line_end=line_start,
        origin=Origin.LLM,
        confidence=confidence,
        severity=Severity.WARNING,
        category=category,
        publishability=Publishability.PUBLISH,
        description="test finding",
    )


def _ann(
    file_path: str,
    line_range: tuple[int, int],
    category: Category = Category.BUG,
) -> AnnotatedFinding:
    return AnnotatedFinding(
        file_path=file_path,
        line_range=line_range,
        category=category,
        severity=Severity.WARNING,
        confidence=Confidence.VERIFIED,
        description="test expected finding",
    )


# ---------------------------------------------------------------------------
# 5-PR test corpus
# ---------------------------------------------------------------------------


_CORPUS_PRS = [
    BenchmarkPR(
        pr_id="org_repo_1",
        repo="org/repo",
        pr_number=1,
        head_sha="aaa",
        base_sha="bbb",
        languages=["python"],
        size="small",
        tags=["bugfix"],
        expected_findings=[_ann("src/auth.py", (42, 42))],
        false_positive_patterns=[],
    ),
    BenchmarkPR(
        pr_id="org_repo_2",
        repo="org/repo",
        pr_number=2,
        head_sha="ccc",
        base_sha="ddd",
        languages=["python"],
        size="medium",
        tags=["api-change"],
        expected_findings=[
            _ann("src/api.py", (10, 20), category=Category.SECURITY),
            _ann("src/api.py", (55, 60), category=Category.BUG),
        ],
        false_positive_patterns=[],
    ),
    BenchmarkPR(
        pr_id="org_repo_3",
        repo="org/repo",
        pr_number=3,
        head_sha="eee",
        base_sha="fff",
        languages=["typescript"],
        size="large",
        tags=["refactor"],
        expected_findings=[_ann("lib/utils.ts", (100, 110))],
        false_positive_patterns=[],
    ),
    BenchmarkPR(
        pr_id="org_repo_4",
        repo="org/repo",
        pr_number=4,
        head_sha="ggg",
        base_sha="hhh",
        languages=["python"],
        size="small",
        tags=["bugfix"],
        # No expected findings — any produced findings are FPs
        expected_findings=[],
        false_positive_patterns=[],
    ),
    BenchmarkPR(
        pr_id="org_repo_5",
        repo="org/repo",
        pr_number=5,
        head_sha="iii",
        base_sha="jjj",
        languages=["python", "typescript"],
        size="medium",
        tags=["refactor", "api-change"],
        expected_findings=[_ann("src/models.py", (200, 210))],
        false_positive_patterns=[],
    ),
]

_CORPUS = Corpus(prs=_CORPUS_PRS)

# Pipeline findings:
# PR1: produces the TP for auth.py:42
# PR2: produces TP for api.py:10-20 (security) + FP on wrong file
# PR3: produces nothing (miss)
# PR4: produces a spurious FP
# PR5: produces TP for models.py:200
_PIPELINE_FINDINGS: dict[str, list[Finding]] = {
    "org_repo_1": [_f("src/auth.py", 42)],
    "org_repo_2": [
        _f("src/api.py", 15, category=Category.SECURITY),  # TP — overlaps (10-20)
        _f("src/other.py", 99),  # FP — wrong file
    ],
    "org_repo_3": [],  # miss
    "org_repo_4": [_f("src/clean.py", 1), _f("src/noise.py", 50)],  # 2 FPs — no expected
    "org_repo_5": [_f("src/models.py", 205)],  # TP — overlaps (200-210)
}


@pytest.mark.asyncio
async def test_run_eval_returns_one_result_per_pr() -> None:
    pipeline = MockPipeline(_PIPELINE_FINDINGS)
    results = await run_eval(_CORPUS, pipeline, variant="structural")
    assert len(results) == 5


@pytest.mark.asyncio
async def test_run_eval_pr_ids_match_corpus_order() -> None:
    pipeline = MockPipeline(_PIPELINE_FINDINGS)
    results = await run_eval(_CORPUS, pipeline)
    returned_ids = [r.pr_id for r in results]
    corpus_ids = [pr.pr_id for pr in _CORPUS_PRS]
    assert returned_ids == corpus_ids


@pytest.mark.asyncio
async def test_run_eval_variant_propagated() -> None:
    pipeline = MockPipeline(_PIPELINE_FINDINGS)
    await run_eval(_CORPUS, pipeline, variant="diff_only")
    assert all(v == "diff_only" for v in pipeline.captured_variants)
    assert len(pipeline.captured_variants) == 5


@pytest.mark.asyncio
async def test_run_eval_correct_tp_fp_miss_counts() -> None:
    pipeline = MockPipeline(_PIPELINE_FINDINGS)
    results = await run_eval(_CORPUS, pipeline, variant="structural")

    by_id: dict[str, EvalResult] = {r.pr_id: r for r in results}

    # PR1: 1 TP, 0 FP, 0 miss
    assert len(by_id["org_repo_1"].true_positives) == 1
    assert len(by_id["org_repo_1"].false_positives) == 0
    assert len(by_id["org_repo_1"].missed) == 0

    # PR2: 1 TP (security on api.py), 1 FP (other.py), 1 miss (bug on api.py:55-60)
    assert len(by_id["org_repo_2"].true_positives) == 1
    assert len(by_id["org_repo_2"].false_positives) == 1
    assert len(by_id["org_repo_2"].missed) == 1

    # PR3: 0 TP, 0 FP, 1 miss
    assert len(by_id["org_repo_3"].true_positives) == 0
    assert len(by_id["org_repo_3"].false_positives) == 0
    assert len(by_id["org_repo_3"].missed) == 1

    # PR4: 0 TP, 2 FP, 0 miss
    assert len(by_id["org_repo_4"].true_positives) == 0
    assert len(by_id["org_repo_4"].false_positives) == 2
    assert len(by_id["org_repo_4"].missed) == 0

    # PR5: 1 TP, 0 FP, 0 miss
    assert len(by_id["org_repo_5"].true_positives) == 1
    assert len(by_id["org_repo_5"].false_positives) == 0
    assert len(by_id["org_repo_5"].missed) == 0


@pytest.mark.asyncio
async def test_compute_metrics_after_run_eval() -> None:
    pipeline = MockPipeline(_PIPELINE_FINDINGS)
    results = await run_eval(_CORPUS, pipeline)
    metrics = compute_metrics(results)
    # accepted_finding_rate = TP / (TP + FP) = 3 / (3 + 3) = 0.5
    # recall = TP / (TP + missed) = 3 / (3 + 2) = 0.6
    assert metrics.total_true_positives == 3
    assert metrics.total_missed == 2
    assert metrics.total_false_positives == 3
    assert metrics.accepted_finding_rate == pytest.approx(3 / 6)
    assert metrics.recall == pytest.approx(3 / 5)


@pytest.mark.asyncio
async def test_write_report_integration(tmp_path: Path) -> None:
    pipeline = MockPipeline(_PIPELINE_FINDINGS)
    results = await run_eval(_CORPUS, pipeline)
    metrics = compute_metrics(results)
    json_path, md_path = write_report(metrics, results, output_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()

    import json

    data = json.loads(json_path.read_text())
    assert data["pr_count"] == 5
    assert data["totals"]["true_positives"] == 3
    assert data["totals"]["false_positives"] == 3
    assert data["totals"]["missed"] == 2
    assert len(data["per_pr"]) == 5


@pytest.mark.asyncio
async def test_empty_corpus_returns_empty_results() -> None:
    pipeline = MockPipeline({})
    results = await run_eval(Corpus(prs=[]), pipeline)
    assert results == []
