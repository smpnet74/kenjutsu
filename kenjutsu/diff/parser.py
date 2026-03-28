"""Unified diff parser.

Parses git unified diff output into structured PatchFile objects with
decoupled per-line old/new line numbers.

Handles:
- Standard add/delete/context hunks
- New files (/dev/null → file)
- Deleted files (file → /dev/null)
- Renames (with and without content changes)
- Binary file markers
- Multi-file diffs
- Empty or malformed input (returns empty list / partial results)
- deletion-omission mode: include_deletions=False strips deletion-only
  hunks and excludes fully-deleted files
"""

from __future__ import annotations

import re

from kenjutsu.diff.models import ChangeType, Hunk, HunkLine, PatchFile

# Matches:  @@ -1,4 +1,4 @@ optional section header
_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


def _strip_path_prefix(path: str) -> str | None:
    """Remove a/ or b/ prefix from git diff paths; return None for /dev/null."""
    if path == "/dev/null":
        return None
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def _parse_hunks(lines: list[str]) -> list[Hunk]:
    """Parse all hunk lines for a single file block."""
    hunks: list[Hunk] = []
    i = 0
    while i < len(lines):
        m = _HUNK_HEADER.match(lines[i])
        if not m:
            i += 1
            continue

        old_start = int(m.group(1))
        old_count = int(m.group(2)) if m.group(2) is not None else 1
        new_start = int(m.group(3))
        new_count = int(m.group(4)) if m.group(4) is not None else 1
        section_header = m.group(5).strip()

        hunk_lines: list[HunkLine] = []
        old_lineno = old_start
        new_lineno = new_start
        i += 1

        while i < len(lines):
            raw = lines[i]
            # Next hunk header — stop consuming
            if _HUNK_HEADER.match(raw):
                break
            # diff --git header — stop consuming (shouldn't happen but guard anyway)
            if raw.startswith("diff --git"):
                break

            if raw.startswith("+"):
                hunk_lines.append(
                    HunkLine(
                        change_type=ChangeType.ADD,
                        content=raw[1:],
                        old_lineno=None,
                        new_lineno=new_lineno,
                    )
                )
                new_lineno += 1
            elif raw.startswith("-"):
                hunk_lines.append(
                    HunkLine(
                        change_type=ChangeType.DELETE,
                        content=raw[1:],
                        old_lineno=old_lineno,
                        new_lineno=None,
                    )
                )
                old_lineno += 1
            elif raw.startswith(" ") or raw == "":
                # Context line (leading space) or blank no-newline line
                hunk_lines.append(
                    HunkLine(
                        change_type=ChangeType.CONTEXT,
                        content=raw[1:] if raw.startswith(" ") else raw,
                        old_lineno=old_lineno,
                        new_lineno=new_lineno,
                    )
                )
                old_lineno += 1
                new_lineno += 1
            elif raw.startswith("\\"):
                # "\ No newline at end of file" — skip marker
                pass
            else:
                # Unknown line within hunk body (shouldn't occur in well-formed diffs)
                pass
            i += 1

        hunks.append(
            Hunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                lines=hunk_lines,
                section_header=section_header,
            )
        )

    return hunks


def parse_diff(diff_text: str, include_deletions: bool = True) -> list[PatchFile]:
    """Parse unified diff text into a list of PatchFile objects.

    Args:
        diff_text: Raw unified diff string (e.g. from `git diff`).
        include_deletions: When False, deletion-only hunks are stripped and
            fully-deleted files are excluded entirely. Useful when the caller
            only wants to review additions.

    Returns:
        Ordered list of PatchFile objects, one per changed file.
    """
    if not diff_text or not diff_text.strip():
        return []

    patches: list[PatchFile] = []
    lines = diff_text.splitlines()

    # Split into per-file blocks on "diff --git" boundaries
    file_block_starts: list[int] = [i for i, ln in enumerate(lines) if ln.startswith("diff --git ")]

    for block_idx, start in enumerate(file_block_starts):
        end = file_block_starts[block_idx + 1] if block_idx + 1 < len(file_block_starts) else len(lines)
        block = lines[start:end]

        old_path: str | None = None
        new_path: str | None = None
        is_binary = False
        rename_from: str | None = None
        rename_to: str | None = None
        hunk_start = len(block)  # index within block where hunks begin

        i = 0
        while i < len(block):
            line = block[i]

            if line.startswith("diff --git "):
                # Extract fallback paths from "diff --git a/X b/Y"
                m = re.match(r"^diff --git a/(.+) b/(.+)$", line)
                if m:
                    old_path = m.group(1)
                    new_path = m.group(2)
            elif line.startswith("--- "):
                raw = line[4:]
                old_path = _strip_path_prefix(raw)
            elif line.startswith("+++ "):
                raw = line[4:]
                new_path = _strip_path_prefix(raw)
                # Hunk content starts after this line
                hunk_start = i + 1
                break
            elif line.startswith("Binary files"):
                is_binary = True
                break
            elif line.startswith("rename from "):
                rename_from = line[len("rename from ") :]
            elif line.startswith("rename to "):
                rename_to = line[len("rename to ") :]
            i += 1

        # Apply rename metadata (overrides --- / +++ when present)
        if rename_from is not None:
            old_path = rename_from
        if rename_to is not None:
            new_path = rename_to

        hunks = _parse_hunks(block[hunk_start:]) if not is_binary else []

        patch = PatchFile(
            old_path=old_path,
            new_path=new_path,
            hunks=hunks,
            is_binary=is_binary,
        )
        patches.append(patch)

    if not include_deletions:
        patches = _apply_deletion_omission(patches)

    return patches


def _apply_deletion_omission(patches: list[PatchFile]) -> list[PatchFile]:
    """Strip deletion-only hunks; exclude fully-deleted files."""
    result: list[PatchFile] = []
    for patch in patches:
        # Exclude files that were entirely deleted
        if patch.is_deleted_file:
            continue
        # Strip hunks that contain only deletions (no additions)
        filtered_hunks = [h for h in patch.hunks if not h.is_deletion_only]
        result.append(
            PatchFile(
                old_path=patch.old_path,
                new_path=patch.new_path,
                hunks=filtered_hunks,
                is_binary=patch.is_binary,
            )
        )
    return result
