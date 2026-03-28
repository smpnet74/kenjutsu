"""Tests for the Finding model and signal taxonomy."""

from kenjutsu.models import (
    Category,
    Confidence,
    Finding,
    Origin,
    Publishability,
    Severity,
)


class TestSignalTaxonomy:
    """Verify the five signal dimensions have the correct values."""

    def test_origin_values(self) -> None:
        assert set(Origin) == {"deterministic", "graph", "llm", "predictive"}

    def test_confidence_values(self) -> None:
        assert set(Confidence) == {"verified", "high", "medium", "low"}

    def test_severity_values(self) -> None:
        assert set(Severity) == {"critical", "warning", "suggestion"}

    def test_category_values(self) -> None:
        expected = {
            "bug",
            "security",
            "breaking-change",
            "performance",
            "missing-test",
            "co-change",
            "stale-doc",
            "style",
        }
        assert set(Category) == expected

    def test_publishability_values(self) -> None:
        assert set(Publishability) == {"publish", "redact-and-publish", "suppress", "audit-only"}


class TestFinding:
    """Verify Finding model behavior."""

    def _make_finding(self, **overrides: object) -> Finding:
        defaults: dict[str, object] = {
            "file_path": "src/auth.py",
            "line_start": 42,
            "line_end": 42,
            "origin": Origin.LLM,
            "confidence": Confidence.HIGH,
            "severity": Severity.WARNING,
            "category": Category.BUG,
            "description": "Potential null dereference on user.email",
        }
        defaults.update(overrides)
        return Finding(**defaults)  # type: ignore[arg-type]

    def test_finding_creation(self) -> None:
        f = self._make_finding()
        assert f.file_path == "src/auth.py"
        assert f.severity == Severity.WARNING
        assert f.publishability == Publishability.PUBLISH  # default

    def test_fingerprint_is_stable(self) -> None:
        f1 = self._make_finding()
        f2 = self._make_finding()
        assert f1.fingerprint == f2.fingerprint

    def test_fingerprint_ignores_line_numbers(self) -> None:
        f1 = self._make_finding(line_start=42, line_end=42)
        f2 = self._make_finding(line_start=99, line_end=105)
        assert f1.fingerprint == f2.fingerprint

    def test_fingerprint_changes_with_file(self) -> None:
        f1 = self._make_finding(file_path="src/auth.py")
        f2 = self._make_finding(file_path="src/middleware.py")
        assert f1.fingerprint != f2.fingerprint

    def test_fingerprint_changes_with_category(self) -> None:
        f1 = self._make_finding(category=Category.BUG)
        f2 = self._make_finding(category=Category.SECURITY)
        assert f1.fingerprint != f2.fingerprint

    def test_fingerprint_case_insensitive(self) -> None:
        f1 = self._make_finding(description="Null dereference")
        f2 = self._make_finding(description="null dereference")
        assert f1.fingerprint == f2.fingerprint

    def test_fingerprint_whitespace_insensitive(self) -> None:
        f1 = self._make_finding(description="Null dereference")
        f2 = self._make_finding(description="  Null  dereference  ")
        assert f1.fingerprint == f2.fingerprint

    def test_evidence_sources_default_empty(self) -> None:
        f = self._make_finding()
        assert f.evidence_sources == []

    def test_evidence_sources_stored(self) -> None:
        f = self._make_finding(evidence_sources=["ast_grep:sql_injection", "graph:taint_path"])
        assert len(f.evidence_sources) == 2

    def test_sensitive_finding_redaction(self) -> None:
        f = self._make_finding(
            category=Category.SECURITY,
            publishability=Publishability.REDACT_AND_PUBLISH,
            description="Hardcoded AWS key found",
        )
        assert f.publishability == Publishability.REDACT_AND_PUBLISH
        assert f.severity == Severity.WARNING  # caller elevates to critical

    def test_predictive_finding(self) -> None:
        f = self._make_finding(
            origin=Origin.PREDICTIVE,
            confidence=Confidence.HIGH,
            category=Category.CO_CHANGE,
            description="File B usually changes with file A (85% probability)",
        )
        assert f.origin == Origin.PREDICTIVE
        assert f.category == Category.CO_CHANGE

    def test_code_context_default_none(self) -> None:
        f = self._make_finding()
        assert f.code_context is None

    def test_fingerprint_without_code_context_matches_original(self) -> None:
        """No code_context → fingerprint equals the original description-only hash."""
        import hashlib

        f = self._make_finding()
        normalized = " ".join(f.description.lower().split())
        expected = hashlib.sha256(f"{f.file_path}:{f.category}:{normalized}".encode()).hexdigest()[:16]
        assert f.fingerprint == expected

    def test_fingerprint_stable_across_llm_rewording(self) -> None:
        """Same code, different LLM description → same fingerprint."""
        code = "if user.email is None: raise ValueError()"
        f1 = self._make_finding(
            description="Potential null dereference on user.email",
            code_context=code,
        )
        f2 = self._make_finding(
            description="Possible NullPointerException when accessing email attribute",
            code_context=code,
        )
        assert f1.fingerprint == f2.fingerprint

    def test_fingerprint_changes_with_different_code(self) -> None:
        """Same description, different code → different fingerprint."""
        f1 = self._make_finding(
            description="Potential null dereference",
            code_context="if user.email is None: raise ValueError()",
        )
        f2 = self._make_finding(
            description="Potential null dereference",
            code_context="if request.body is None: return 400",
        )
        assert f1.fingerprint != f2.fingerprint

    def test_fingerprint_with_code_context_differs_from_without(self) -> None:
        """Adding code_context changes the fingerprint (different hash formula)."""
        f_no_ctx = self._make_finding()
        f_with_ctx = self._make_finding(code_context="if user.email is None: raise ValueError()")
        assert f_no_ctx.fingerprint != f_with_ctx.fingerprint

    def test_fingerprint_ignores_line_numbers_with_code_context(self) -> None:
        code = "if user.email is None: raise ValueError()"
        f1 = self._make_finding(line_start=10, line_end=10, code_context=code)
        f2 = self._make_finding(line_start=99, line_end=105, code_context=code)
        assert f1.fingerprint == f2.fingerprint
