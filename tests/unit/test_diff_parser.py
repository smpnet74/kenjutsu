"""Tests for unified diff parser.

Coverage: PatchFile/Hunk/HunkLine models, parse_diff function,
edge cases: binary files, renames, new files, deletions, empty/malformed input,
deletion-omission mode.
"""

import textwrap

from kenjutsu.diff import parse_diff
from kenjutsu.diff.models import ChangeType, Hunk, HunkLine, PatchFile

# ---------------------------------------------------------------------------
# Fixtures — raw diff strings
# ---------------------------------------------------------------------------

SIMPLE_MODIFY = textwrap.dedent("""\
    diff --git a/foo.py b/foo.py
    index abc1234..def5678 100644
    --- a/foo.py
    +++ b/foo.py
    @@ -1,4 +1,4 @@
     line one
    -line two
    +line TWO
     line three
     line four
""")

TWO_HUNKS = textwrap.dedent("""\
    diff --git a/bar.py b/bar.py
    index 0000000..1111111 100644
    --- a/bar.py
    +++ b/bar.py
    @@ -1,3 +1,4 @@
     alpha
    +beta
     gamma
     delta
    @@ -10,3 +11,2 @@ def my_func():
     epsilon
    -zeta
     eta
""")

NEW_FILE = textwrap.dedent("""\
    diff --git a/new.py b/new.py
    new file mode 100644
    index 0000000..aabbccd
    --- /dev/null
    +++ b/new.py
    @@ -0,0 +1,3 @@
    +hello
    +world
    +!
""")

DELETED_FILE = textwrap.dedent("""\
    diff --git a/gone.py b/gone.py
    deleted file mode 100644
    index aabbccd..0000000
    --- a/gone.py
    +++ /dev/null
    @@ -1,3 +0,0 @@
    -hello
    -world
    -!
""")

RENAME_ONLY = textwrap.dedent("""\
    diff --git a/old_name.py b/new_name.py
    similarity index 100%
    rename from old_name.py
    rename to new_name.py
""")

RENAME_WITH_CHANGES = textwrap.dedent("""\
    diff --git a/old.py b/new.py
    similarity index 80%
    rename from old.py
    rename to new.py
    index 1111111..2222222 100644
    --- a/old.py
    +++ b/new.py
    @@ -1,3 +1,3 @@
     context
    -old content
    +new content
     more context
""")

BINARY_FILE = textwrap.dedent("""\
    diff --git a/image.png b/image.png
    index abc1234..def5678 100644
    Binary files a/image.png and b/image.png differ
""")

MULTI_FILE = textwrap.dedent("""\
    diff --git a/alpha.py b/alpha.py
    index 0000000..1111111 100644
    --- a/alpha.py
    +++ b/alpha.py
    @@ -1,2 +1,2 @@
    -old
    +new
     context
    diff --git a/beta.py b/beta.py
    index 2222222..3333333 100644
    --- a/beta.py
    +++ b/beta.py
    @@ -5,2 +5,3 @@
     unchanged
    +added line
     also unchanged
""")

SECTION_HEADER = textwrap.dedent("""\
    diff --git a/module.py b/module.py
    index 0000000..1111111 100644
    --- a/module.py
    +++ b/module.py
    @@ -10,4 +10,4 @@ def compute(x):
     result = x * 2
    -return result
    +return result + 1
     pass
     # end
""")

ONLY_DELETIONS_HUNK = textwrap.dedent("""\
    diff --git a/mixed.py b/mixed.py
    index 0000000..1111111 100644
    --- a/mixed.py
    +++ b/mixed.py
    @@ -1,4 +1,4 @@
     context
    -removed line
    +replacement line
     still here
     and more
    @@ -10,3 +10,1 @@
    -only deletions
    -in this hunk
     remaining
""")


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestHunkLineModel:
    def test_add_line(self) -> None:
        line = HunkLine(change_type=ChangeType.ADD, content="new line", old_lineno=None, new_lineno=5)
        assert line.change_type == ChangeType.ADD
        assert line.content == "new line"
        assert line.old_lineno is None
        assert line.new_lineno == 5

    def test_delete_line(self) -> None:
        line = HunkLine(change_type=ChangeType.DELETE, content="old line", old_lineno=3, new_lineno=None)
        assert line.change_type == ChangeType.DELETE
        assert line.old_lineno == 3
        assert line.new_lineno is None

    def test_context_line_has_both_linenos(self) -> None:
        line = HunkLine(change_type=ChangeType.CONTEXT, content="same", old_lineno=7, new_lineno=7)
        assert line.old_lineno == 7
        assert line.new_lineno == 7


class TestHunkModel:
    def test_basic_construction(self) -> None:
        hunk = Hunk(old_start=1, old_count=3, new_start=1, new_count=4, lines=[], section_header="")
        assert hunk.old_start == 1
        assert hunk.old_count == 3

    def test_is_deletion_only_false_when_has_additions(self) -> None:
        hunk = Hunk(
            old_start=1,
            old_count=2,
            new_start=1,
            new_count=2,
            lines=[
                HunkLine(ChangeType.DELETE, "old", old_lineno=1, new_lineno=None),
                HunkLine(ChangeType.ADD, "new", old_lineno=None, new_lineno=1),
            ],
            section_header="",
        )
        assert not hunk.is_deletion_only

    def test_is_deletion_only_true_when_only_deletes_and_context(self) -> None:
        hunk = Hunk(
            old_start=1,
            old_count=3,
            new_start=1,
            new_count=2,
            lines=[
                HunkLine(ChangeType.CONTEXT, "ctx", old_lineno=1, new_lineno=1),
                HunkLine(ChangeType.DELETE, "gone", old_lineno=2, new_lineno=None),
                HunkLine(ChangeType.CONTEXT, "ctx2", old_lineno=3, new_lineno=2),
            ],
            section_header="",
        )
        assert hunk.is_deletion_only


class TestPatchFileModel:
    def test_is_new_file(self) -> None:
        pf = PatchFile(old_path=None, new_path="new.py", hunks=[], is_binary=False)
        assert pf.is_new_file
        assert not pf.is_deleted_file

    def test_is_deleted_file(self) -> None:
        pf = PatchFile(old_path="gone.py", new_path=None, hunks=[], is_binary=False)
        assert pf.is_deleted_file
        assert not pf.is_new_file

    def test_is_rename(self) -> None:
        pf = PatchFile(old_path="old.py", new_path="new.py", hunks=[], is_binary=False)
        assert pf.is_rename

    def test_same_path_not_rename(self) -> None:
        pf = PatchFile(old_path="same.py", new_path="same.py", hunks=[], is_binary=False)
        assert not pf.is_rename

    def test_additions_count(self) -> None:
        hunk = Hunk(
            old_start=1,
            old_count=1,
            new_start=1,
            new_count=3,
            lines=[
                HunkLine(ChangeType.CONTEXT, "ctx", old_lineno=1, new_lineno=1),
                HunkLine(ChangeType.ADD, "a", old_lineno=None, new_lineno=2),
                HunkLine(ChangeType.ADD, "b", old_lineno=None, new_lineno=3),
            ],
            section_header="",
        )
        pf = PatchFile(old_path="f.py", new_path="f.py", hunks=[hunk], is_binary=False)
        assert pf.additions == 2
        assert pf.deletions == 0

    def test_deletions_count(self) -> None:
        hunk = Hunk(
            old_start=1,
            old_count=2,
            new_start=1,
            new_count=1,
            lines=[
                HunkLine(ChangeType.DELETE, "x", old_lineno=1, new_lineno=None),
                HunkLine(ChangeType.CONTEXT, "y", old_lineno=2, new_lineno=1),
            ],
            section_header="",
        )
        pf = PatchFile(old_path="f.py", new_path="f.py", hunks=[hunk], is_binary=False)
        assert pf.deletions == 1
        assert pf.additions == 0


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestParseDiffEmptyAndMalformed:
    def test_empty_string_returns_empty_list(self) -> None:
        assert parse_diff("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert parse_diff("   \n  ") == []

    def test_malformed_diff_without_hunks_parsed_as_binary_or_empty(self) -> None:
        diff = "diff --git a/foo b/foo\nsome random lines\n"
        result = parse_diff(diff)
        # Should produce one patch file with no hunks (not crash)
        assert len(result) == 1
        assert result[0].hunks == []


class TestParseDiffSimpleModify:
    def test_returns_one_patch_file(self) -> None:
        result = parse_diff(SIMPLE_MODIFY)
        assert len(result) == 1

    def test_file_paths(self) -> None:
        pf = parse_diff(SIMPLE_MODIFY)[0]
        assert pf.old_path == "foo.py"
        assert pf.new_path == "foo.py"

    def test_not_binary(self) -> None:
        pf = parse_diff(SIMPLE_MODIFY)[0]
        assert not pf.is_binary

    def test_one_hunk(self) -> None:
        pf = parse_diff(SIMPLE_MODIFY)[0]
        assert len(pf.hunks) == 1

    def test_hunk_header_positions(self) -> None:
        hunk = parse_diff(SIMPLE_MODIFY)[0].hunks[0]
        assert hunk.old_start == 1
        assert hunk.old_count == 4
        assert hunk.new_start == 1
        assert hunk.new_count == 4

    def test_hunk_lines_count(self) -> None:
        hunk = parse_diff(SIMPLE_MODIFY)[0].hunks[0]
        assert len(hunk.lines) == 5  # 1 ctx, 1 del, 1 add, 2 ctx

    def test_hunk_line_types(self) -> None:
        lines = parse_diff(SIMPLE_MODIFY)[0].hunks[0].lines
        assert lines[0].change_type == ChangeType.CONTEXT
        assert lines[1].change_type == ChangeType.DELETE
        assert lines[2].change_type == ChangeType.ADD
        assert lines[3].change_type == ChangeType.CONTEXT

    def test_hunk_line_content(self) -> None:
        lines = parse_diff(SIMPLE_MODIFY)[0].hunks[0].lines
        assert lines[1].content == "line two"
        assert lines[2].content == "line TWO"

    def test_delete_line_has_old_lineno(self) -> None:
        lines = parse_diff(SIMPLE_MODIFY)[0].hunks[0].lines
        del_line = lines[1]
        assert del_line.old_lineno == 2
        assert del_line.new_lineno is None

    def test_add_line_has_new_lineno(self) -> None:
        lines = parse_diff(SIMPLE_MODIFY)[0].hunks[0].lines
        add_line = lines[2]
        assert add_line.new_lineno == 2
        assert add_line.old_lineno is None

    def test_context_line_has_both_linenos(self) -> None:
        lines = parse_diff(SIMPLE_MODIFY)[0].hunks[0].lines
        assert lines[0].old_lineno == 1
        assert lines[0].new_lineno == 1
        assert lines[4].old_lineno == 4
        assert lines[4].new_lineno == 4

    def test_additions_and_deletions_counts(self) -> None:
        pf = parse_diff(SIMPLE_MODIFY)[0]
        assert pf.additions == 1
        assert pf.deletions == 1


class TestParseDiffTwoHunks:
    def test_two_hunks_parsed(self) -> None:
        pf = parse_diff(TWO_HUNKS)[0]
        assert len(pf.hunks) == 2

    def test_second_hunk_positions(self) -> None:
        hunk = parse_diff(TWO_HUNKS)[0].hunks[1]
        assert hunk.old_start == 10
        assert hunk.new_start == 11

    def test_section_header_captured(self) -> None:
        hunk = parse_diff(TWO_HUNKS)[0].hunks[1]
        assert "my_func" in hunk.section_header


class TestParseDiffNewFile:
    def test_new_file_old_path_is_none(self) -> None:
        pf = parse_diff(NEW_FILE)[0]
        assert pf.old_path is None

    def test_new_file_new_path_set(self) -> None:
        pf = parse_diff(NEW_FILE)[0]
        assert pf.new_path == "new.py"

    def test_new_file_is_new_file(self) -> None:
        pf = parse_diff(NEW_FILE)[0]
        assert pf.is_new_file

    def test_new_file_lines_are_all_additions(self) -> None:
        hunk = parse_diff(NEW_FILE)[0].hunks[0]
        assert all(ln.change_type == ChangeType.ADD for ln in hunk.lines)

    def test_new_file_additions_count(self) -> None:
        pf = parse_diff(NEW_FILE)[0]
        assert pf.additions == 3
        assert pf.deletions == 0


class TestParseDiffDeletedFile:
    def test_deleted_file_new_path_is_none(self) -> None:
        pf = parse_diff(DELETED_FILE)[0]
        assert pf.new_path is None

    def test_deleted_file_old_path_set(self) -> None:
        pf = parse_diff(DELETED_FILE)[0]
        assert pf.old_path == "gone.py"

    def test_deleted_file_is_deleted_file(self) -> None:
        pf = parse_diff(DELETED_FILE)[0]
        assert pf.is_deleted_file

    def test_deleted_file_lines_are_all_deletions(self) -> None:
        hunk = parse_diff(DELETED_FILE)[0].hunks[0]
        assert all(ln.change_type == ChangeType.DELETE for ln in hunk.lines)

    def test_deleted_file_deletions_count(self) -> None:
        pf = parse_diff(DELETED_FILE)[0]
        assert pf.deletions == 3
        assert pf.additions == 0


class TestParseDiffRename:
    def test_rename_only_paths(self) -> None:
        pf = parse_diff(RENAME_ONLY)[0]
        assert pf.old_path == "old_name.py"
        assert pf.new_path == "new_name.py"

    def test_rename_only_is_rename(self) -> None:
        pf = parse_diff(RENAME_ONLY)[0]
        assert pf.is_rename

    def test_rename_only_no_hunks(self) -> None:
        pf = parse_diff(RENAME_ONLY)[0]
        assert pf.hunks == []

    def test_rename_with_changes_paths(self) -> None:
        pf = parse_diff(RENAME_WITH_CHANGES)[0]
        assert pf.old_path == "old.py"
        assert pf.new_path == "new.py"

    def test_rename_with_changes_has_hunk(self) -> None:
        pf = parse_diff(RENAME_WITH_CHANGES)[0]
        assert len(pf.hunks) == 1


class TestParseDiffBinary:
    def test_binary_file_is_binary(self) -> None:
        pf = parse_diff(BINARY_FILE)[0]
        assert pf.is_binary

    def test_binary_file_paths(self) -> None:
        pf = parse_diff(BINARY_FILE)[0]
        assert pf.old_path == "image.png"
        assert pf.new_path == "image.png"

    def test_binary_file_no_hunks(self) -> None:
        pf = parse_diff(BINARY_FILE)[0]
        assert pf.hunks == []


class TestParseDiffMultiFile:
    def test_two_files_returned(self) -> None:
        result = parse_diff(MULTI_FILE)
        assert len(result) == 2

    def test_first_file_path(self) -> None:
        result = parse_diff(MULTI_FILE)
        assert result[0].new_path == "alpha.py"

    def test_second_file_path(self) -> None:
        result = parse_diff(MULTI_FILE)
        assert result[1].new_path == "beta.py"

    def test_each_file_has_one_hunk(self) -> None:
        result = parse_diff(MULTI_FILE)
        assert len(result[0].hunks) == 1
        assert len(result[1].hunks) == 1


class TestParseDiffSectionHeader:
    def test_section_header_preserved(self) -> None:
        pf = parse_diff(SECTION_HEADER)[0]
        assert "compute" in pf.hunks[0].section_header


class TestParseDiffDeletionOmission:
    """include_deletions=False: strip deletion-only hunks; skip deleted files."""

    def test_include_deletions_true_keeps_all_hunks(self) -> None:
        result = parse_diff(ONLY_DELETIONS_HUNK, include_deletions=True)
        assert len(result[0].hunks) == 2

    def test_include_deletions_false_strips_deletion_only_hunks(self) -> None:
        result = parse_diff(ONLY_DELETIONS_HUNK, include_deletions=False)
        # First hunk has an addition (context + delete + context still kept because it has context)
        # Second hunk has only deletions + context → should be stripped
        pf = result[0]
        assert len(pf.hunks) == 1

    def test_include_deletions_false_keeps_hunk_with_additions(self) -> None:
        result = parse_diff(ONLY_DELETIONS_HUNK, include_deletions=False)
        hunk = result[0].hunks[0]
        # The remaining hunk must contain at least one non-delete line
        assert any(ln.change_type != ChangeType.DELETE for ln in hunk.lines)

    def test_deleted_file_excluded_when_include_deletions_false(self) -> None:
        result = parse_diff(DELETED_FILE, include_deletions=False)
        assert result == []

    def test_new_file_kept_when_include_deletions_false(self) -> None:
        result = parse_diff(NEW_FILE, include_deletions=False)
        assert len(result) == 1

    def test_simple_modify_kept_when_include_deletions_false(self) -> None:
        result = parse_diff(SIMPLE_MODIFY, include_deletions=False)
        assert len(result) == 1

    def test_rename_only_kept_when_include_deletions_false(self) -> None:
        # Rename-only has no hunks, not a deleted file — should be kept for awareness
        result = parse_diff(RENAME_ONLY, include_deletions=False)
        assert len(result) == 1


class TestLinenumberAccuracy:
    """Line numbers must be correct for the decoupled old/new views."""

    def test_line_numbers_in_two_hunk_file(self) -> None:
        pf = parse_diff(TWO_HUNKS)[0]
        hunk1 = pf.hunks[0]
        hunk2 = pf.hunks[1]

        # hunk1: @@ -1,3 +1,4 @@
        #  alpha   old=1 new=1
        # +beta    old=None new=2
        #  gamma   old=2 new=3
        #  delta   old=3 new=4
        alpha = hunk1.lines[0]
        beta = hunk1.lines[1]
        gamma = hunk1.lines[2]

        assert alpha.old_lineno == 1 and alpha.new_lineno == 1
        assert beta.old_lineno is None and beta.new_lineno == 2
        assert gamma.old_lineno == 2 and gamma.new_lineno == 3

        # hunk2: @@ -10,3 +11,2 @@
        #  epsilon   old=10 new=11
        # -zeta      old=11 new=None
        #  eta       old=12 new=12
        epsilon = hunk2.lines[0]
        zeta = hunk2.lines[1]
        eta = hunk2.lines[2]

        assert epsilon.old_lineno == 10 and epsilon.new_lineno == 11
        assert zeta.old_lineno == 11 and zeta.new_lineno is None
        assert eta.old_lineno == 12 and eta.new_lineno == 12
