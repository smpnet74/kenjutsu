"""Pydantic models for .kenjutsu.yaml configuration.

Resolution order: repo config > Kenjutsu defaults.
All fields have defaults so zero-config always works.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SeverityThreshold(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"


class ConfidenceThreshold(StrEnum):
    VERIFIED = "verified"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewConfig(BaseModel):
    auto: bool = True
    severity_threshold: SeverityThreshold = SeverityThreshold.WARNING
    confidence_threshold: ConfidenceThreshold = ConfidenceThreshold.HIGH
    max_findings: int = 20
    predictive_warnings: bool = True

    model_config = {"extra": "ignore"}


class IgnoreConfig(BaseModel):
    paths: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class ModelsConfig(BaseModel):
    primary: str = "auto"

    model_config = {"extra": "ignore"}


class RepoConfig(BaseModel):
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    ignore: IgnoreConfig = Field(default_factory=IgnoreConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)

    model_config = {"extra": "ignore"}
