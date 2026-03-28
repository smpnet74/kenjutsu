"""Pipeline orchestration package.

Business logic lives here as plain async functions — no DBOS imports.
The thin step/workflow wrappers that add durability live in steps.py.
"""

from kenjutsu.pipeline.sha_guard import (
    GuardResult,
    PrRef,
    check_sha_current,
    entry_guard,
    exit_guard,
)

__all__ = [
    "GuardResult",
    "PrRef",
    "check_sha_current",
    "entry_guard",
    "exit_guard",
]
