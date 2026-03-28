"""Tree-sitter AST context extension for diff hunks.

For each hunk in a PatchFile, this module uses tree-sitter to find the
innermost enclosing function or class scope, then records it on the hunk's
``enclosing_scope`` field.

Supported languages
-------------------
First-class (TypeScript/JavaScript and Python):
    Fully resolved scope — function, method, class, nested functions.

Basic (Go, Java, Rust):
    Enclosing function/method/class resolved; decorators and complex
    patterns may produce simpler names.

Fallback:
    When the file extension is unsupported or a grammar import fails,
    ``enclosing_scope`` is left as None on every hunk.  This is a
    documented, expected state — callers must tolerate None.

Thread safety
-------------
Each ``extend_hunks_with_ast`` call creates its own ``tree_sitter.Parser``
instance.  Language objects are shared globals but are read-only after
initialisation, so concurrent calls are safe.
"""

from __future__ import annotations

import logging
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from tree_sitter import Language, Node, Parser

from kenjutsu.diff.models import Hunk, PatchFile, ScopeContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language registry
# ---------------------------------------------------------------------------

# Maps lowercase language name → (loader_fn, scope_node_kinds, body_field_names)
#
# scope_node_kinds: node types that represent a named scope (function, class …)
# body_field_names: field names for the scope body — used to extract the
#                   signature as everything *before* the body starts.
_LANGUAGE_CONFIGS: dict[str, tuple[str, set[str], set[str]]] = {
    "python": (
        "tree_sitter_python",
        {
            "function_definition",
            "class_definition",
            "decorated_definition",
        },
        {"body"},
    ),
    "javascript": (
        "tree_sitter_javascript",
        {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "class_declaration",
            "class_expression",
            "method_definition",
        },
        {"body"},
    ),
    "typescript": (
        "tree_sitter_typescript",
        {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "class_declaration",
            "class_expression",
            "method_definition",
            "abstract_method_signature",
        },
        {"body"},
    ),
    "tsx": (
        "tree_sitter_typescript",
        {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "class_declaration",
            "class_expression",
            "method_definition",
        },
        {"body"},
    ),
    "go": (
        "tree_sitter_go",
        {
            "function_declaration",
            "method_declaration",
        },
        {"body"},
    ),
    "java": (
        "tree_sitter_java",
        {
            "method_declaration",
            "class_declaration",
            "interface_declaration",
            "constructor_declaration",
        },
        {"body"},
    ),
    "rust": (
        "tree_sitter_rust",
        {
            "function_item",
            "impl_item",
            "struct_item",
            "trait_item",
        },
        {"body"},
    ),
}

# Extension → language name
_EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
}

# ---------------------------------------------------------------------------
# Kind mapping: tree-sitter node type → human label
# ---------------------------------------------------------------------------
_KIND_MAP: dict[str, str] = {
    "function_definition": "function",
    "function_declaration": "function",
    "function_expression": "function",
    "arrow_function": "function",
    "function_item": "function",
    "class_definition": "class",
    "class_declaration": "class",
    "class_expression": "class",
    "decorated_definition": "function",  # Python decorated — inspect inner
    "method_definition": "method",
    "method_declaration": "method",
    "abstract_method_signature": "method",
    "constructor_declaration": "constructor",
    "interface_declaration": "interface",
    "struct_item": "struct",
    "impl_item": "impl",
    "trait_item": "trait",
}


# ---------------------------------------------------------------------------
# Language loader (cached)
# ---------------------------------------------------------------------------


@cache
def _load_language(lang_name: str) -> Language | None:
    """Import and return the tree-sitter Language for *lang_name*.

    Returns None when the grammar package is unavailable so that callers
    can fall back gracefully.
    """
    config = _LANGUAGE_CONFIGS.get(lang_name)
    if config is None:
        return None
    module_name, _, _ = config
    try:
        import importlib

        mod = importlib.import_module(module_name)
        # tree-sitter-typescript exposes language_typescript / language_tsx
        if lang_name in ("typescript", "tsx"):
            fn_name = "language_tsx" if lang_name == "tsx" else "language_typescript"
            language_fn: Callable[[], object] = getattr(mod, fn_name)
        else:
            language_fn = mod.language
        return Language(language_fn())
    except Exception:
        logger.warning("tree-sitter grammar unavailable for %s — falling back", lang_name)
        return None


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _detect_language(file_path: str) -> str | None:
    """Return the language name for *file_path*, or None if unsupported."""
    ext = Path(file_path).suffix.lower()
    return _EXT_TO_LANGUAGE.get(ext)


def _extract_signature(node: Node, source_lines: list[bytes], lang_name: str) -> str:
    """Return the declaration signature for *node*.

    The signature is everything from the node's first line up to (but not
    including) the body block.  For nodes without a body field (e.g.
    arrow functions with expression bodies), the first source line is used.
    """
    config = _LANGUAGE_CONFIGS.get(lang_name)
    body_fields = config[2] if config else {"body"}

    body_child: Node | None = None
    for field in body_fields:
        body_child = node.child_by_field_name(field)
        if body_child is not None:
            break

    start_row = node.start_point[0]

    if body_child is not None:
        body_row = body_child.start_point[0]
        # Signature spans from node start to the line before the body.
        sig_rows = source_lines[start_row:body_row]
    else:
        sig_rows = [source_lines[start_row]] if start_row < len(source_lines) else []

    # Decode and strip trailing whitespace / braces from last line.
    sig_lines = [line.decode("utf-8", errors="replace").rstrip() for line in sig_rows]
    return "\n".join(sig_lines).strip()


def _extract_name(node: Node, lang_name: str) -> str:
    """Return the name of the scope node, or an empty string if unnamed."""
    # For decorated_definition (Python), dig into the wrapped definition.
    if node.type == "decorated_definition":
        for child in node.children:
            if child.type in ("function_definition", "class_definition", "async_function_definition"):
                return _extract_name(child, lang_name)

    name_node = node.child_by_field_name("name")
    if name_node and name_node.text is not None:
        return name_node.text.decode("utf-8", errors="replace")

    # Fallback: first identifier child.
    for child in node.children:
        if child.type == "identifier" and child.text is not None:
            return child.text.decode("utf-8", errors="replace")

    return "<anonymous>"


def _find_innermost_scope(
    node: Node,
    target_start: int,
    target_end: int,
    scope_kinds: set[str],
) -> Node | None:
    """Walk the AST and return the innermost scope node that fully contains
    [target_start, target_end] (0-indexed row numbers).

    A scope node *contains* the target if its row range includes both
    target_start and target_end.
    """
    node_start = node.start_point[0]
    node_end = node.end_point[0]

    if node_start > target_end or node_end < target_start:
        # This node is entirely outside the target range — prune.
        return None

    best: Node | None = None

    # Check children first (depth-first, innermost wins).
    for child in node.children:
        candidate = _find_innermost_scope(child, target_start, target_end, scope_kinds)
        if candidate is not None:
            if best is None:
                best = candidate
            else:
                # Prefer smaller (more specific) scope.
                cand_size = candidate.end_point[0] - candidate.start_point[0]
                best_size = best.end_point[0] - best.start_point[0]
                if cand_size < best_size:
                    best = candidate

    if best is not None:
        return best

    # If no child scope matched, check whether *this* node is a scope.
    if node.type in scope_kinds and node_start <= target_start and node_end >= target_end:
        return node

    return None


def _build_scope_context(
    node: Node,
    source_lines: list[bytes],
    lang_name: str,
) -> ScopeContext:
    kind = _KIND_MAP.get(node.type, node.type)
    name = _extract_name(node, lang_name)
    signature = _extract_signature(node, source_lines, lang_name)
    return ScopeContext(
        kind=kind,
        name=name,
        signature=signature,
        start_line=node.start_point[0] + 1,  # convert to 1-based
        end_line=node.end_point[0] + 1,
        language=lang_name,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_enclosing_scope(
    source: str | bytes,
    hunk: Hunk,
    lang_name: str,
) -> ScopeContext | None:
    """Parse *source* and return the innermost scope enclosing *hunk*.

    Parameters
    ----------
    source:
        Full source text of the file (str or bytes).
    hunk:
        The diff hunk whose new-file line range is used for the search.
    lang_name:
        Language name as returned by :func:`_detect_language`.

    Returns
    -------
    ScopeContext or None
        None when no enclosing scope is found (top-level code) or when
        the language grammar is unavailable.
    """
    language = _load_language(lang_name)
    if language is None:
        return None

    config = _LANGUAGE_CONFIGS[lang_name]
    scope_kinds = config[1]

    source_bytes = source.encode("utf-8") if isinstance(source, str) else source

    parser = Parser(language)
    tree = parser.parse(source_bytes)
    source_lines = source_bytes.splitlines(keepends=True)

    # Convert 1-based hunk line numbers to 0-based for tree-sitter.
    hunk_start_0 = hunk.new_start - 1
    hunk_end_0 = hunk.new_start + max(hunk.new_count - 1, 0) - 1
    hunk_end_0 = max(hunk_start_0, hunk_end_0)

    scope_node = _find_innermost_scope(tree.root_node, hunk_start_0, hunk_end_0, scope_kinds)
    if scope_node is None:
        return None

    return _build_scope_context(scope_node, source_lines, lang_name)


def extend_hunks_with_ast(
    patches: list[PatchFile],
    file_content_getter: Callable[[str], str | bytes | None],
) -> list[PatchFile]:
    """Extend every hunk in *patches* with its enclosing AST scope.

    Parameters
    ----------
    patches:
        Parsed diff — a list of PatchFile objects (from the 1.4a parser).
    file_content_getter:
        Callable that accepts a file path (str) and returns the full source
        content of that file, or None if the file is unavailable.  The path
        passed is ``patch.path`` — the new-version path.

    Returns
    -------
    The same list of PatchFile objects, mutated in place with
    ``enclosing_scope`` populated where possible.  Hunks whose scope
    cannot be determined are left with ``enclosing_scope = None``.
    """
    for patch in patches:
        if patch.is_binary or patch.is_deletion or not patch.hunks:
            continue

        lang_name = _detect_language(patch.path)
        if lang_name is None:
            continue

        language = _load_language(lang_name)
        if language is None:
            continue

        source = file_content_getter(patch.path)
        if source is None:
            logger.debug("file content unavailable for %s — skipping AST extension", patch.path)
            continue

        config = _LANGUAGE_CONFIGS[lang_name]
        scope_kinds = config[1]

        source_bytes = source.encode("utf-8") if isinstance(source, str) else source

        parser = Parser(language)
        try:
            tree = parser.parse(source_bytes)
        except Exception:
            logger.warning("tree-sitter parse failed for %s — skipping", patch.path)
            continue

        source_lines = source_bytes.splitlines(keepends=True)

        for hunk in patch.hunks:
            hunk_start_0 = hunk.new_start - 1
            hunk_end_0 = hunk.new_start + max(hunk.new_count - 1, 0) - 1
            hunk_end_0 = max(hunk_start_0, hunk_end_0)

            scope_node = _find_innermost_scope(tree.root_node, hunk_start_0, hunk_end_0, scope_kinds)
            if scope_node is not None:
                hunk.enclosing_scope = _build_scope_context(scope_node, source_lines, lang_name)

    return patches
