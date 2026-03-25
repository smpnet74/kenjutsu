"""Tests for the slash command parser."""

import pytest

from kenjutsu.server.commands import CommandKind, ParsedCommand, ParseError, parse_command


class TestParseCommandReturnsNone:
    """Comments without a /kenjutsu prefix should return None."""

    def test_empty_comment_returns_none(self) -> None:
        assert parse_command("") is None

    def test_unrelated_comment_returns_none(self) -> None:
        assert parse_command("LGTM, looks good to me!") is None

    def test_partial_match_returns_none(self) -> None:
        assert parse_command("kenjutsu review") is None  # missing leading slash

    def test_different_slash_command_returns_none(self) -> None:
        assert parse_command("/github review") is None


class TestParseReviewFull:
    """/kenjutsu review triggers a full review."""

    def test_review_no_file(self) -> None:
        result = parse_command("/kenjutsu review")
        assert result == ParsedCommand(kind=CommandKind.REVIEW, file_path=None)

    def test_review_no_file_trailing_whitespace(self) -> None:
        result = parse_command("  /kenjutsu review  ")
        assert result == ParsedCommand(kind=CommandKind.REVIEW, file_path=None)

    def test_review_in_multiline_comment(self) -> None:
        # Command on its own line within a multi-line comment body
        body = "Hey team,\n\n/kenjutsu review\n\nThanks"
        result = parse_command(body)
        assert result == ParsedCommand(kind=CommandKind.REVIEW, file_path=None)

    def test_command_mid_sentence_is_ignored(self) -> None:
        # /kenjutsu not at the start of a line is not a command
        body = "Could you /kenjutsu review this?"
        assert parse_command(body) is None

    def test_review_on_its_own_line(self) -> None:
        body = "Please run:\n/kenjutsu review\nThanks"
        result = parse_command(body)
        assert result == ParsedCommand(kind=CommandKind.REVIEW, file_path=None)


class TestParseReviewScoped:
    """/kenjutsu review <file> triggers a scoped review."""

    def test_review_with_simple_filename(self) -> None:
        result = parse_command("/kenjutsu review auth.py")
        assert result == ParsedCommand(kind=CommandKind.REVIEW, file_path="auth.py")

    def test_review_with_path(self) -> None:
        result = parse_command("/kenjutsu review src/auth.py")
        assert result == ParsedCommand(kind=CommandKind.REVIEW, file_path="src/auth.py")

    def test_review_with_nested_path(self) -> None:
        result = parse_command("/kenjutsu review kenjutsu/server/commands.py")
        assert result == ParsedCommand(kind=CommandKind.REVIEW, file_path="kenjutsu/server/commands.py")

    def test_review_file_strips_surrounding_whitespace(self) -> None:
        result = parse_command("  /kenjutsu review   src/auth.py  ")
        assert result == ParsedCommand(kind=CommandKind.REVIEW, file_path="src/auth.py")


class TestParseIgnore:
    """/kenjutsu ignore suppresses a finding."""

    def test_ignore_command(self) -> None:
        result = parse_command("/kenjutsu ignore")
        assert result == ParsedCommand(kind=CommandKind.IGNORE, file_path=None)

    def test_ignore_with_trailing_whitespace(self) -> None:
        result = parse_command("  /kenjutsu ignore  ")
        assert result == ParsedCommand(kind=CommandKind.IGNORE, file_path=None)

    def test_ignore_in_multiline_comment(self) -> None:
        body = "This finding is wrong.\n/kenjutsu ignore"
        result = parse_command(body)
        assert result == ParsedCommand(kind=CommandKind.IGNORE, file_path=None)


class TestParseErrors:
    """Malformed or unknown commands raise ParseError."""

    def test_bare_kenjutsu_raises(self) -> None:
        with pytest.raises(ParseError, match="missing subcommand"):
            parse_command("/kenjutsu")

    def test_bare_kenjutsu_whitespace_raises(self) -> None:
        with pytest.raises(ParseError, match="missing subcommand"):
            parse_command("  /kenjutsu  ")

    def test_unknown_subcommand_raises(self) -> None:
        with pytest.raises(ParseError, match="unknown command"):
            parse_command("/kenjutsu foo")

    def test_unknown_subcommand_in_multiline_raises(self) -> None:
        with pytest.raises(ParseError, match="unknown command"):
            parse_command("Hey\n/kenjutsu frobnicate\nbye")

    def test_mid_sentence_kenjutsu_not_a_command(self) -> None:
        # A /kenjutsu mid-sentence is not a command, even if subcommand looks valid
        assert parse_command("I mean /kenjutsu badcmd here") is None

    def test_review_too_many_args_raises(self) -> None:
        with pytest.raises(ParseError, match="too many arguments"):
            parse_command("/kenjutsu review file1.py file2.py")

    def test_ignore_with_args_raises(self) -> None:
        with pytest.raises(ParseError, match="too many arguments"):
            parse_command("/kenjutsu ignore some/file.py")

    def test_first_command_wins_when_second_is_malformed(self) -> None:
        # Only first /kenjutsu occurrence is parsed
        with pytest.raises(ParseError, match="unknown command"):
            parse_command("/kenjutsu badcmd\n/kenjutsu review")
