"""Tests for .kenjutsu.yaml parser and RepoConfig model.

TDD: all tests written before implementation.
"""

from __future__ import annotations

from kenjutsu.config import load_repo_config
from kenjutsu.config.models import (
    ConfidenceThreshold,
    IgnoreConfig,
    ModelsConfig,
    RepoConfig,
    ReviewConfig,
    SeverityThreshold,
)


class TestRepoConfigDefaults:
    """Missing .kenjutsu.yaml → all defaults applied."""

    def test_none_content_returns_defaults(self) -> None:
        config = load_repo_config(None)
        assert isinstance(config, RepoConfig)

    def test_default_review_auto_is_true(self) -> None:
        config = load_repo_config(None)
        assert config.review.auto is True

    def test_default_severity_threshold_is_warning(self) -> None:
        config = load_repo_config(None)
        assert config.review.severity_threshold == SeverityThreshold.WARNING

    def test_default_confidence_threshold_is_high(self) -> None:
        config = load_repo_config(None)
        assert config.review.confidence_threshold == ConfidenceThreshold.HIGH

    def test_default_max_findings_is_20(self) -> None:
        config = load_repo_config(None)
        assert config.review.max_findings == 20

    def test_default_predictive_warnings_is_true(self) -> None:
        config = load_repo_config(None)
        assert config.review.predictive_warnings is True

    def test_default_ignore_paths_is_empty(self) -> None:
        config = load_repo_config(None)
        assert config.ignore.paths == []

    def test_default_ignore_categories_is_empty(self) -> None:
        config = load_repo_config(None)
        assert config.ignore.categories == []

    def test_default_models_primary_is_auto(self) -> None:
        config = load_repo_config(None)
        assert config.models.primary == "auto"

    def test_empty_string_returns_defaults(self) -> None:
        config = load_repo_config("")
        assert config.review.auto is True
        assert config.review.max_findings == 20

    def test_empty_yaml_document_returns_defaults(self) -> None:
        config = load_repo_config("---\n")
        assert config.review.auto is True


class TestPartialOverride:
    """Partial .kenjutsu.yaml → specified values override, unspecified use defaults."""

    def test_partial_review_section_overrides_auto(self) -> None:
        yaml = "review:\n  auto: false\n"
        config = load_repo_config(yaml)
        assert config.review.auto is False

    def test_partial_review_section_keeps_other_defaults(self) -> None:
        yaml = "review:\n  auto: false\n"
        config = load_repo_config(yaml)
        assert config.review.max_findings == 20
        assert config.review.severity_threshold == SeverityThreshold.WARNING

    def test_override_severity_threshold_to_critical(self) -> None:
        yaml = "review:\n  severity_threshold: critical\n"
        config = load_repo_config(yaml)
        assert config.review.severity_threshold == SeverityThreshold.CRITICAL

    def test_override_confidence_threshold_to_medium(self) -> None:
        yaml = "review:\n  confidence_threshold: medium\n"
        config = load_repo_config(yaml)
        assert config.review.confidence_threshold == ConfidenceThreshold.MEDIUM

    def test_override_max_findings(self) -> None:
        yaml = "review:\n  max_findings: 5\n"
        config = load_repo_config(yaml)
        assert config.review.max_findings == 5

    def test_ignore_paths_specified(self) -> None:
        yaml = 'ignore:\n  paths:\n    - "vendor/**"\n    - "*.generated.go"\n'
        config = load_repo_config(yaml)
        assert config.ignore.paths == ["vendor/**", "*.generated.go"]

    def test_ignore_categories_specified(self) -> None:
        yaml = "ignore:\n  categories:\n    - style\n"
        config = load_repo_config(yaml)
        assert config.ignore.categories == ["style"]

    def test_ignore_paths_specified_keeps_default_categories(self) -> None:
        yaml = 'ignore:\n  paths:\n    - "vendor/**"\n'
        config = load_repo_config(yaml)
        assert config.ignore.categories == []

    def test_models_primary_override(self) -> None:
        yaml = "models:\n  primary: gpt-4o\n"
        config = load_repo_config(yaml)
        assert config.models.primary == "gpt-4o"

    def test_only_models_section_keeps_review_defaults(self) -> None:
        yaml = "models:\n  primary: claude-3-5-sonnet\n"
        config = load_repo_config(yaml)
        assert config.review.auto is True
        assert config.review.max_findings == 20

    def test_full_config_all_overridden(self) -> None:
        yaml = (
            "review:\n"
            "  auto: false\n"
            "  severity_threshold: critical\n"
            "  confidence_threshold: verified\n"
            "  max_findings: 10\n"
            "  predictive_warnings: false\n"
            "ignore:\n"
            "  paths:\n"
            '    - "dist/**"\n'
            "  categories:\n"
            "    - style\n"
            "    - performance\n"
            "models:\n"
            "  primary: gpt-4o\n"
        )
        config = load_repo_config(yaml)
        assert config.review.auto is False
        assert config.review.severity_threshold == SeverityThreshold.CRITICAL
        assert config.review.confidence_threshold == ConfidenceThreshold.VERIFIED
        assert config.review.max_findings == 10
        assert config.review.predictive_warnings is False
        assert config.ignore.paths == ["dist/**"]
        assert config.ignore.categories == ["style", "performance"]
        assert config.models.primary == "gpt-4o"


class TestInvalidYamlHandling:
    """Invalid YAML → clear error logged, returns defaults."""

    def test_invalid_yaml_returns_defaults(self) -> None:
        config = load_repo_config("invalid: [yaml: }")
        assert isinstance(config, RepoConfig)
        assert config.review.auto is True

    def test_invalid_yaml_returns_default_max_findings(self) -> None:
        config = load_repo_config("review:\n  max_findings: [not a number]")
        # Pydantic validation failure → fall back to defaults
        assert config.review.max_findings == 20

    def test_invalid_yaml_syntax_error_returns_defaults(self) -> None:
        config = load_repo_config("review:\n  auto: true\n  - broken")
        assert config.review.auto is True

    def test_unknown_keys_are_ignored(self) -> None:
        yaml = "review:\n  auto: false\n  unknown_field: xyz\n"
        config = load_repo_config(yaml)
        assert config.review.auto is False

    def test_extra_top_level_keys_ignored(self) -> None:
        yaml = "review:\n  auto: false\nfuture_feature:\n  enabled: true\n"
        config = load_repo_config(yaml)
        assert config.review.auto is False

    def test_invalid_severity_value_returns_defaults(self) -> None:
        yaml = "review:\n  severity_threshold: not_a_severity\n"
        config = load_repo_config(yaml)
        assert config.review.severity_threshold == SeverityThreshold.WARNING


class TestModelStructure:
    """RepoConfig model structure and types."""

    def test_review_config_is_review_config_type(self) -> None:
        config = load_repo_config(None)
        assert isinstance(config.review, ReviewConfig)

    def test_ignore_config_is_ignore_config_type(self) -> None:
        config = load_repo_config(None)
        assert isinstance(config.ignore, IgnoreConfig)

    def test_models_config_is_models_config_type(self) -> None:
        config = load_repo_config(None)
        assert isinstance(config.models, ModelsConfig)

    def test_severity_threshold_values(self) -> None:
        assert SeverityThreshold.CRITICAL == "critical"
        assert SeverityThreshold.WARNING == "warning"
        assert SeverityThreshold.SUGGESTION == "suggestion"

    def test_confidence_threshold_values(self) -> None:
        assert ConfidenceThreshold.VERIFIED == "verified"
        assert ConfidenceThreshold.HIGH == "high"
        assert ConfidenceThreshold.MEDIUM == "medium"
        assert ConfidenceThreshold.LOW == "low"
