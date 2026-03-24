"""Finding model with the five-dimensional signal taxonomy.

Every finding carries independent dimensions of origin, confidence,
severity, category, and publishability. These are the canonical enums
used throughout the system — one source of truth.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field


class Origin(StrEnum):
    """How the finding was produced."""

    DETERMINISTIC = "deterministic"
    GRAPH = "graph"
    LLM = "llm"
    PREDICTIVE = "predictive"


class Confidence(StrEnum):
    """How certain we are the finding is correct."""

    VERIFIED = "verified"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Severity(StrEnum):
    """How important it is to fix. One canonical enum everywhere."""

    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"


class Category(StrEnum):
    """What kind of finding."""

    BUG = "bug"
    SECURITY = "security"
    BREAKING_CHANGE = "breaking-change"
    PERFORMANCE = "performance"
    MISSING_TEST = "missing-test"
    CO_CHANGE = "co-change"
    STALE_DOC = "stale-doc"
    STYLE = "style"


class Publishability(StrEnum):
    """Whether and how to show the finding."""

    PUBLISH = "publish"
    REDACT_AND_PUBLISH = "redact-and-publish"
    SUPPRESS = "suppress"
    AUDIT_ONLY = "audit-only"


class Finding(BaseModel):
    """A single review finding with the full signal taxonomy."""

    file_path: str
    line_start: int
    line_end: int
    origin: Origin
    confidence: Confidence
    severity: Severity
    category: Category
    publishability: Publishability = Publishability.PUBLISH
    description: str
    suggestion: str | None = None
    evidence_sources: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fingerprint(self) -> str:
        """Stable identifier for dedup, suppression, and FP tracking.

        Uses file_path + category + normalized description. Line numbers
        are intentionally excluded — code can shift lines without
        changing the finding.
        """
        normalized = " ".join(self.description.lower().split())
        raw = f"{self.file_path}:{self.category}:{normalized}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
