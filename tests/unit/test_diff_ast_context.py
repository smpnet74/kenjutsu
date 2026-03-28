"""Unit tests for the tree-sitter AST context extension (DEM-156 / 1.4b).

Test coverage
-------------
- Python: top-level function, class method, nested function, decorated function,
  top-level code (no enclosing scope)
- TypeScript/JavaScript: function declaration, class method, arrow function,
  top-level code
- Go: function declaration, method declaration
- Java: class method, constructor
- Rust: free function, impl method
- Unsupported language: graceful None fallback
- extend_hunks_with_ast: multi-file batch, missing file content, binary patch skip
"""

from __future__ import annotations

from kenjutsu.diff.ast_context import extend_hunks_with_ast, find_enclosing_scope
from kenjutsu.diff.models import Hunk, PatchFile, ScopeContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hunk(new_start: int, new_count: int = 3) -> Hunk:
    """Create a minimal Hunk positioned at new_start."""
    return Hunk(old_start=new_start, old_count=new_count, new_start=new_start, new_count=new_count, lines=[])


def _patch(path: str, hunks: list[Hunk]) -> PatchFile:
    return PatchFile(old_path=None, new_path=path, hunks=hunks)


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

PYTHON_TOP_LEVEL_FUNC = """\
def greet(name: str) -> str:
    message = f"Hello, {name}"
    return message
"""

PYTHON_CLASS_WITH_METHOD = """\
class Calculator:
    def __init__(self, value: int) -> None:
        self.value = value

    def add(self, x: int) -> int:
        result = self.value + x
        return result
"""

PYTHON_NESTED_FUNC = """\
def outer(n: int) -> int:
    def inner(x: int) -> int:
        return x * 2
    return inner(n)
"""

PYTHON_DECORATED_FUNC = """\
import functools

def my_decorator(fn):
    return fn

@my_decorator
def decorated(x: int) -> int:
    return x + 1
"""

PYTHON_TOP_LEVEL_CODE = """\
import os

x = 1
y = x + 2
print(y)
"""


class TestPython:
    def test_top_level_function(self) -> None:
        hunk = _hunk(new_start=2, new_count=2)  # inside greet
        scope = find_enclosing_scope(PYTHON_TOP_LEVEL_FUNC, hunk, "python")
        assert scope is not None
        assert scope.kind == "function"
        assert scope.name == "greet"
        assert scope.language == "python"
        assert scope.start_line == 1

    def test_class_method(self) -> None:
        hunk = _hunk(new_start=6, new_count=2)  # inside add()
        scope = find_enclosing_scope(PYTHON_CLASS_WITH_METHOD, hunk, "python")
        assert scope is not None
        assert scope.kind in ("function", "method")
        assert scope.name == "add"

    def test_class_method_prefers_method_over_class(self) -> None:
        """The innermost scope (method) should be returned, not the class."""
        hunk = _hunk(new_start=6, new_count=2)
        scope = find_enclosing_scope(PYTHON_CLASS_WITH_METHOD, hunk, "python")
        assert scope is not None
        assert scope.name == "add", "Expected the method, not the class"

    def test_nested_inner_function(self) -> None:
        hunk = _hunk(new_start=3, new_count=1)  # inside inner()
        scope = find_enclosing_scope(PYTHON_NESTED_FUNC, hunk, "python")
        assert scope is not None
        assert scope.name == "inner"

    def test_nested_outer_function_line(self) -> None:
        hunk = _hunk(new_start=4, new_count=1)  # outer's return line
        scope = find_enclosing_scope(PYTHON_NESTED_FUNC, hunk, "python")
        assert scope is not None
        assert scope.name == "outer"

    def test_decorated_function(self) -> None:
        hunk = _hunk(new_start=8, new_count=1)  # inside decorated()
        scope = find_enclosing_scope(PYTHON_DECORATED_FUNC, hunk, "python")
        assert scope is not None
        # decorated_definition or function_definition — either is acceptable
        assert scope.name in ("decorated", "my_decorator")

    def test_top_level_code_no_scope(self) -> None:
        hunk = _hunk(new_start=3, new_count=2)  # x = 1; y = x + 2
        scope = find_enclosing_scope(PYTHON_TOP_LEVEL_CODE, hunk, "python")
        assert scope is None

    def test_signature_contains_def(self) -> None:
        hunk = _hunk(new_start=2, new_count=1)
        scope = find_enclosing_scope(PYTHON_TOP_LEVEL_FUNC, hunk, "python")
        assert scope is not None
        assert "greet" in scope.signature


# ---------------------------------------------------------------------------
# TypeScript / JavaScript
# ---------------------------------------------------------------------------

TS_SOURCE = """\
class UserService {
    private users: string[] = [];

    addUser(name: string): void {
        this.users.push(name);
    }

    getUser(index: number): string {
        return this.users[index];
    }
}

function formatName(first: string, last: string): string {
    return `${first} ${last}`;
}

const greet = (name: string): string => {
    return `Hello, ${name}!`;
};
"""

JS_SOURCE = """\
function add(a, b) {
    return a + b;
}

class Counter {
    constructor(start) {
        this.count = start;
    }

    increment() {
        this.count += 1;
        return this.count;
    }
}

const double = (x) => x * 2;
"""


class TestTypeScript:
    def test_class_method(self) -> None:
        hunk = _hunk(new_start=5, new_count=1)  # inside addUser
        scope = find_enclosing_scope(TS_SOURCE, hunk, "typescript")
        assert scope is not None
        assert scope.name == "addUser"
        assert scope.kind == "method"

    def test_free_function(self) -> None:
        hunk = _hunk(new_start=14, new_count=1)  # inside formatName
        scope = find_enclosing_scope(TS_SOURCE, hunk, "typescript")
        assert scope is not None
        assert scope.name == "formatName"
        assert scope.kind == "function"

    def test_arrow_function(self) -> None:
        hunk = _hunk(new_start=18, new_count=1)  # inside greet arrow fn
        scope = find_enclosing_scope(TS_SOURCE, hunk, "typescript")
        assert scope is not None
        assert scope.kind == "function"

    def test_top_level_code_ts(self) -> None:
        source = "const x = 1;\nconst y = x + 2;\n"
        hunk = _hunk(new_start=1, new_count=1)
        scope = find_enclosing_scope(source, hunk, "typescript")
        assert scope is None


class TestJavaScript:
    def test_free_function(self) -> None:
        hunk = _hunk(new_start=2, new_count=1)
        scope = find_enclosing_scope(JS_SOURCE, hunk, "javascript")
        assert scope is not None
        assert scope.name == "add"

    def test_constructor(self) -> None:
        hunk = _hunk(new_start=7, new_count=1)
        scope = find_enclosing_scope(JS_SOURCE, hunk, "javascript")
        assert scope is not None
        assert scope.name in ("constructor", "Counter")

    def test_class_method_increment(self) -> None:
        hunk = _hunk(new_start=11, new_count=2)
        scope = find_enclosing_scope(JS_SOURCE, hunk, "javascript")
        assert scope is not None
        assert scope.name == "increment"


# ---------------------------------------------------------------------------
# Go
# ---------------------------------------------------------------------------

GO_SOURCE = """\
package main

type Server struct {
    host string
    port int
}

func NewServer(host string, port int) *Server {
    return &Server{host: host, port: port}
}

func (s *Server) Start() error {
    // bind and listen
    return nil
}
"""


class TestGo:
    def test_free_function(self) -> None:
        hunk = _hunk(new_start=9, new_count=1)  # inside NewServer
        scope = find_enclosing_scope(GO_SOURCE, hunk, "go")
        assert scope is not None
        assert scope.name == "NewServer"
        assert scope.kind == "function"

    def test_method(self) -> None:
        hunk = _hunk(new_start=14, new_count=1)  # inside Start()
        scope = find_enclosing_scope(GO_SOURCE, hunk, "go")
        assert scope is not None
        assert scope.name == "Start"
        assert scope.kind == "method"


# ---------------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------------

JAVA_SOURCE = """\
public class OrderService {

    private final List<String> orders = new ArrayList<>();

    public OrderService() {
        // default constructor
    }

    public void placeOrder(String item) {
        orders.add(item);
    }

    public String getOrder(int index) {
        return orders.get(index);
    }
}
"""


class TestJava:
    def test_method(self) -> None:
        hunk = _hunk(new_start=10, new_count=1)  # inside placeOrder
        scope = find_enclosing_scope(JAVA_SOURCE, hunk, "java")
        assert scope is not None
        assert scope.name == "placeOrder"
        assert scope.kind == "method"

    def test_constructor(self) -> None:
        hunk = _hunk(new_start=6, new_count=1)  # inside constructor
        scope = find_enclosing_scope(JAVA_SOURCE, hunk, "java")
        assert scope is not None
        assert scope.kind in ("constructor", "method", "class")


# ---------------------------------------------------------------------------
# Rust
# ---------------------------------------------------------------------------

RUST_SOURCE = """\
pub struct Config {
    pub host: String,
    pub port: u16,
}

impl Config {
    pub fn new(host: &str, port: u16) -> Self {
        Config {
            host: host.to_string(),
            port,
        }
    }

    pub fn validate(&self) -> bool {
        !self.host.is_empty() && self.port > 0
    }
}

pub fn default_config() -> Config {
    Config::new("localhost", 8080)
}
"""


class TestRust:
    def test_impl_method(self) -> None:
        hunk = _hunk(new_start=8, new_count=3)  # inside Config::new
        scope = find_enclosing_scope(RUST_SOURCE, hunk, "rust")
        assert scope is not None
        assert scope.name == "new"
        assert scope.kind == "function"

    def test_free_function(self) -> None:
        hunk = _hunk(new_start=20, new_count=1)  # inside default_config
        scope = find_enclosing_scope(RUST_SOURCE, hunk, "rust")
        assert scope is not None
        assert scope.name == "default_config"


# ---------------------------------------------------------------------------
# Unsupported language / fallback
# ---------------------------------------------------------------------------


class TestFallback:
    def test_unsupported_extension_returns_none(self) -> None:
        """Ruby source with .rb extension has no grammar → None."""
        hunk = _hunk(new_start=2, new_count=1)
        scope = find_enclosing_scope("def foo\n  1 + 1\nend\n", hunk, "ruby")
        assert scope is None

    def test_unknown_lang_name_returns_none(self) -> None:
        hunk = _hunk(new_start=1, new_count=1)
        scope = find_enclosing_scope("x = 1", hunk, "cobol")
        assert scope is None


# ---------------------------------------------------------------------------
# extend_hunks_with_ast — integration with PatchFile
# ---------------------------------------------------------------------------


class TestExtendHunksWithAst:
    def test_python_file_gets_scope(self) -> None:
        hunk = _hunk(new_start=2, new_count=2)
        patch = _patch("service.py", [hunk])

        def getter(path: str) -> str:
            return PYTHON_TOP_LEVEL_FUNC

        result = extend_hunks_with_ast([patch], getter)
        assert result[0].hunks[0].enclosing_scope is not None
        assert result[0].hunks[0].enclosing_scope.name == "greet"

    def test_multiple_hunks_different_scopes(self) -> None:
        hunk_func = _hunk(new_start=6, new_count=2)  # inside add()
        hunk_init = _hunk(new_start=2, new_count=2)  # inside __init__
        patch = _patch("calc.py", [hunk_init, hunk_func])

        def getter(path: str) -> str:
            return PYTHON_CLASS_WITH_METHOD

        extend_hunks_with_ast([patch], getter)
        names = [h.enclosing_scope.name if h.enclosing_scope else None for h in patch.hunks]
        assert "__init__" in names
        assert "add" in names

    def test_missing_file_content_leaves_none(self) -> None:
        hunk = _hunk(new_start=2, new_count=1)
        patch = _patch("missing.py", [hunk])

        def getter(path: str) -> None:
            return None

        extend_hunks_with_ast([patch], getter)
        assert patch.hunks[0].enclosing_scope is None

    def test_binary_patch_skipped(self) -> None:
        hunk = _hunk(new_start=1, new_count=1)
        patch = PatchFile(old_path=None, new_path="image.png", hunks=[hunk], is_binary=True)

        def getter(path: str) -> str:
            return ""

        extend_hunks_with_ast([patch], getter)
        assert patch.hunks[0].enclosing_scope is None

    def test_deletion_patch_skipped(self) -> None:
        hunk = _hunk(new_start=1, new_count=1)
        patch = PatchFile(old_path="old.py", new_path=None, hunks=[hunk])

        def getter(path: str) -> str:
            return PYTHON_TOP_LEVEL_FUNC

        extend_hunks_with_ast([patch], getter)
        assert patch.hunks[0].enclosing_scope is None

    def test_unsupported_language_skipped(self) -> None:
        hunk = _hunk(new_start=2, new_count=1)
        patch = _patch("script.sh", [hunk])

        def getter(path: str) -> str:
            return "#!/bin/bash\necho hello\n"

        extend_hunks_with_ast([patch], getter)
        assert patch.hunks[0].enclosing_scope is None

    def test_multi_file_batch(self) -> None:
        patches = [
            _patch("a.py", [_hunk(new_start=2, new_count=1)]),
            _patch("b.ts", [_hunk(new_start=14, new_count=1)]),
        ]

        sources = {
            "a.py": PYTHON_TOP_LEVEL_FUNC,
            "b.ts": TS_SOURCE,
        }

        extend_hunks_with_ast(patches, lambda p: sources.get(p))

        py_scope = patches[0].hunks[0].enclosing_scope
        ts_scope = patches[1].hunks[0].enclosing_scope

        assert py_scope is not None and py_scope.language == "python"
        assert ts_scope is not None and ts_scope.language == "typescript"

    def test_scope_context_fields_populated(self) -> None:
        hunk = _hunk(new_start=2, new_count=1)
        patch = _patch("svc.py", [hunk])
        extend_hunks_with_ast([patch], lambda _: PYTHON_TOP_LEVEL_FUNC)

        scope: ScopeContext | None = patch.hunks[0].enclosing_scope
        assert scope is not None
        assert scope.kind in ("function", "class", "method")
        assert isinstance(scope.name, str) and scope.name
        assert isinstance(scope.signature, str) and scope.signature
        assert scope.start_line >= 1
        assert scope.end_line >= scope.start_line
        assert scope.language == "python"
