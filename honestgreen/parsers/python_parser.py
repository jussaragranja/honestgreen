"""Extract pytest / unittest test cases from Python source using the stdlib ast."""
from __future__ import annotations

import ast
import copy
import re

from honestgreen.model import Assertion, TestCase

SKIP_DECORATOR = re.compile(r"(pytest\.mark\.(skip|skipif|xfail)|unittest\.skip\w*|^skip\w*)")
SKIP_CALLS = {"pytest.skip", "pytest.xfail", "self.skipTest", "unittest.skip"}

STRONG_ASSERT_METHODS = {
    "assertEqual", "assertEquals", "assertNotEqual", "assertAlmostEqual", "assertRaises",
    "assertRaisesRegex", "assertCountEqual", "assertListEqual", "assertDictEqual",
    "assertSetEqual", "assertTupleEqual", "assertSequenceEqual", "assertMultiLineEqual",
    "assertIs", "assertWarns",
}
RELATIONAL_ASSERT_METHODS = {
    "assertIn", "assertNotIn", "assertGreater", "assertGreaterEqual", "assertLess",
    "assertLessEqual", "assertRegex", "assertIsInstance",
}
WEAK_ASSERT_METHODS = {"assertTrue", "assertFalse", "assertIsNotNone", "assertIsNone", "assertIsNot"}


def _norm(text: str) -> str:
    return " ".join(text.split())


class _LiteralMasker(ast.NodeTransformer):
    def __init__(self) -> None:
        self.literals: list = []

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        self.literals.append(node.value)
        return ast.copy_location(ast.Name(id="__LIT__", ctx=ast.Load()), node)


def _assertion(node: ast.AST, strength: int) -> Assertion:
    text = _norm(ast.unparse(node))
    masker = _LiteralMasker()
    skeleton = _norm(ast.unparse(masker.visit(copy.deepcopy(node))))
    return Assertion(text=text, skeleton=skeleton, literals=tuple(masker.literals),
                     strength=strength, line=getattr(node, "lineno", 0))


def _assert_strength(test: ast.expr) -> int:
    if isinstance(test, ast.Compare):
        ops = test.ops
        if any(isinstance(op, (ast.Is, ast.IsNot)) for op in ops):
            comparators = [test.left, *test.comparators]
            if any(isinstance(c, ast.Constant) and c.value is None for c in comparators):
                return 1
            return 3
        if all(isinstance(op, (ast.Eq, ast.NotEq)) for op in ops):
            return 3
        return 2
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return 1
    if isinstance(test, ast.Call) and isinstance(test.func, ast.Name) and test.func.id == "isinstance":
        return 1
    return 1  # bare truthiness: `assert x`, `assert f()`


def _call_name(call: ast.Call) -> str:
    try:
        return ast.unparse(call.func)
    except Exception:  # pragma: no cover - defensive
        return ""


def _collect(func: ast.AST) -> tuple[list[Assertion], set[str]]:
    assertions: list[Assertion] = []
    skips: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            assertions.append(_assertion(node, _assert_strength(node.test)))
        elif isinstance(node, ast.With):
            for item in node.items:
                expr = item.context_expr
                if isinstance(expr, ast.Call) and _call_name(expr) in ("pytest.raises", "pytest.warns"):
                    assertions.append(_assertion(expr, 3))
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            short = name.rsplit(".", 1)[-1]
            if name in SKIP_CALLS:
                skips.add(_norm(ast.unparse(node)))
            elif name.startswith("self.") and short in STRONG_ASSERT_METHODS:
                assertions.append(_assertion(node, 3))
            elif name.startswith("self.") and short in RELATIONAL_ASSERT_METHODS:
                assertions.append(_assertion(node, 2))
            elif name.startswith("self.") and short in WEAK_ASSERT_METHODS:
                assertions.append(_assertion(node, 1))
            elif short.startswith("assert_") and "mock" not in name.lower():
                assertions.append(_assertion(node, 2))
    return assertions, skips


def _skip_decorators(node: ast.AST) -> set[str]:
    out = set()
    for dec in getattr(node, "decorator_list", []):
        text = _norm(ast.unparse(dec))
        if SKIP_DECORATOR.search(text):
            out.add(text)
    return out


def _pytestmark(body: list[ast.stmt]) -> set[str]:
    out = set()
    for stmt in body:
        if isinstance(stmt, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "pytestmark" for t in stmt.targets):
            text = _norm(ast.unparse(stmt.value))
            if SKIP_DECORATOR.search(text):
                out.add(f"pytestmark = {text}")
    return out


def parse(source: str, path: str) -> dict[str, TestCase]:
    """Return {test name: TestCase}. Returns {} if the file does not parse."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    module_skips = _pytestmark(tree.body)
    tests: dict[str, TestCase] = {}

    def add(func: ast.AST, prefix: str, inherited: set[str]) -> None:
        assertions, body_skips = _collect(func)
        name = f"{prefix}{func.name}"
        tests[name] = TestCase(
            name=name, file=path, line=func.lineno,
            source=_norm(ast.unparse(func)), assertions=assertions,
            skip_markers=inherited | _skip_decorators(func) | body_skips,
        )

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            add(node, "", module_skips)
        elif isinstance(node, ast.ClassDef) and (node.name.startswith("Test") or any(
                "TestCase" in ast.unparse(b) for b in node.bases)):
            inherited = module_skips | _skip_decorators(node) | _pytestmark(node.body)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test"):
                    add(item, f"{node.name}.", inherited)
    return tests
