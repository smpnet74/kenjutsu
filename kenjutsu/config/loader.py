"""Load and parse .kenjutsu.yaml into a RepoConfig.

Fallback behaviour: any parse or validation error returns defaults
with a logged warning. Never raises — caller always gets a usable config.
"""

from __future__ import annotations

import logging

import yaml
from pydantic import ValidationError

from .models import RepoConfig

logger = logging.getLogger(__name__)

_DEFAULTS = RepoConfig()


def load_repo_config(yaml_content: str | None) -> RepoConfig:
    """Parse .kenjutsu.yaml content and return a RepoConfig with defaults applied.

    Args:
        yaml_content: Raw YAML string from the repo's .kenjutsu.yaml, or None if
                      the file is absent.

    Returns:
        RepoConfig with repo-specified values merged over Kenjutsu defaults.
        Never raises — invalid/missing content falls back to full defaults.
    """
    if not yaml_content or not yaml_content.strip():
        return RepoConfig()

    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        logger.warning("Failed to parse .kenjutsu.yaml: %s — using defaults", exc)
        return RepoConfig()

    if data is None:
        return RepoConfig()

    if not isinstance(data, dict):
        logger.warning("Unexpected .kenjutsu.yaml structure (got %s) — using defaults", type(data).__name__)
        return RepoConfig()

    try:
        return RepoConfig.model_validate(data)
    except ValidationError as exc:
        logger.warning(".kenjutsu.yaml validation failed: %s — using defaults", exc)
        return RepoConfig()
