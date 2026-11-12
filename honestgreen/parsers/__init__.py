"""Language parsers and test-file detection."""
from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath

from honestgreen.model import TestCase
from honestgreen.parsers import java_parser, js_parser, python_parser

JS_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts")

DEFAULT_TEST_PATTERNS = (
    "test_*.py", "*_test.py", "tests/**/*.py", "**/tests/**/*.py",
    "src/test/**/*.java", "**/src/test/**/*.java", "*Test.java", "*Tests.java", "*IT.java",
) + tuple(p for ext in JS_EXTENSIONS for p in (
    f"*.test{ext}", f"*.spec{ext}", f"__tests__/*{ext}", f"**/__tests__/*{ext}", f"**/__tests__/**/*{ext}", f"__tests__/**/*{ext}",
    f"test/*{ext}", f"test/**/*{ext}", f"tests/*{ext}", f"tests/**/*{ext}",
))


def language(path: str) -> str | None:
    if path.endswith(".py"):
        return "python"
    if path.endswith(".java"):
        return "java"
    if path.endswith(JS_EXTENSIONS) and not path.endswith((".d.ts", ".d.mts", ".d.cts")):
        return "javascript"
    return None


def is_test_file(path: str, patterns=DEFAULT_TEST_PATTERNS) -> bool:
    if language(path) is None:
        return False
    p = PurePosixPath(path)
    return any(fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(p.name, pat) for pat in patterns)


def parse(source: str, path: str) -> dict[str, TestCase]:
    lang = language(path)
    if lang == "python":
        return python_parser.parse(source, path)
    if lang == "java":
        return java_parser.parse(source, path)
    if lang == "javascript":
        return js_parser.parse(source, path)
    return {}
