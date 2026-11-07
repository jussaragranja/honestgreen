"""Language parsers and test-file detection."""
from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath

from honestgreen.model import TestCase
from honestgreen.parsers import java_parser, python_parser

DEFAULT_TEST_PATTERNS = (
    "test_*.py", "*_test.py", "tests/**/*.py", "**/tests/**/*.py",
    "src/test/**/*.java", "**/src/test/**/*.java", "*Test.java", "*Tests.java", "*IT.java",
)


def language(path: str) -> str | None:
    if path.endswith(".py"):
        return "python"
    if path.endswith(".java"):
        return "java"
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
    return {}
