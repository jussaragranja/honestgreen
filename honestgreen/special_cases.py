"""HG006: production code special-cased for a test's values.

The textbook way to make a failing test pass without implementing the rule is to
recognise the test's input and return the test's expected value:

    if subtotal == Decimal("57.30"):         # input used by the test
        return Decimal("18.90")              # what the test expects

A new branch is reported when, in an existing production file:
  - its condition is an equality (==, ===, equals, in, is, case) with a literal that is
    not trivial (not 0-10, booleans, null or one-character strings) and not already in the file;
  - the branch produces a non-trivial literal (same line, or the next lines: return / assignment);
  - a test that existed before the change, and was not modified by it, uses both values;
  - the specification does not mention the condition value (a documented rule is legitimate).

A test written or edited in the same change is not enough: a new branch tested with its own
values is ordinary development (and an edited test is reported by HG001-HG005).
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from honestgreen.values import CODE_LITERAL, normalize

TRIVIAL = {"true", "false", "null", "none", "undefined", ""}
IF_PY = re.compile(r"^\s*(?:if|elif|while)\s+(.+?):\s*(.*)$")
IF_C = re.compile(r"^\s*(?:\}\s*)?(?:else\s+)?(?:if|while)\s*\(")
CASE = re.compile(r"^\s*case\s+(.+?)\s*(?::|->)\s*(.*)$")
TERNARY_PY = re.compile(r"(?:return\s+|=\s*|\(\s*)?(.+?)\s+if\s+(.+?)\s+else\s+")
TERNARY_C = re.compile(r"([^?]+?)\s\?\s(.+?)\s:\s")
EQUALITY = re.compile(r"(?<![!<>=])===?(?!=)|\.equals(?:IgnoreCase)?\(|\bequals\(|(?<!not )\bin\b|\bis\b(?! not)")
RESULT_LINE = re.compile(r"^\s*(?:return\b|yield\b|[\w.\[\]'\"]+\s*(?:=|\+=)(?!=)|->)")
CONDITIONAL = re.compile(r"^\s*(?:\}\s*)?(?:if|elif|else|case|switch|match|while|for)\b")


@dataclass
class SpecialCase:
    line: int
    text: str            # the added source lines (condition and result)
    conditions: list[str]  # normalized literals in the condition
    results: list[str]     # normalized literals produced by the branch


def trivial(value: str) -> bool:
    if value.lower() in TRIVIAL or len(value) < 2 and not value.isdigit():
        return True
    try:
        number = Decimal(value)
    except InvalidOperation:
        return False
    return number == number.to_integral_value() and abs(number) <= 10


def literals(text: str) -> list[str]:
    return [normalize(lit) for lit in CODE_LITERAL.findall(text)]


def strip_comment(line: str) -> str:
    """Drop a trailing `//` or `#` comment that is outside string literals."""
    quote = None
    for k, ch in enumerate(line):
        if quote:
            if ch == "\\":
                continue
            if ch == quote and line[k - 1] != "\\":
                quote = None
        elif ch in "\"'`":
            quote = ch
        elif line.startswith("//", k) or ch == "#" and (k == 0 or line[k - 1] in " \t"):
            return line[:k]
    return line


def _parens(line: str, start: int) -> int:
    depth = 0
    for k in range(start, len(line)):
        if line[k] == "(":
            depth += 1
        elif line[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    return len(line) - 1


def _split(line: str) -> tuple[str, str] | None:
    """(condition, same-line result) of a conditional line, or None."""
    if m := CASE.match(line):
        return "== " + m.group(1), m.group(2)
    if m := IF_C.match(line):          # also Python's `if (x == 1):`
        close = _parens(line, m.end() - 1)
        return line[m.end():close], line[close + 1:].strip(" {:")
    if m := IF_PY.match(line):
        return m.group(1), m.group(2)
    if m := TERNARY_C.search(line):
        return m.group(1), m.group(2)
    if m := TERNARY_PY.search(line):
        return m.group(2), m.group(1)
    return None


def find(before_src: str | None, after_src: str | None) -> list[SpecialCase]:
    """New equality branches with literal conditions and literal results."""
    if not before_src or not after_src:
        return []
    a, b = before_src.splitlines(), after_src.splitlines()
    known = set(literals(before_src))
    out: list[SpecialCase] = []
    for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag not in ("insert", "replace"):
            continue
        for j in range(j1, j2):
            parts = _split(strip_comment(b[j]))
            if not parts:
                continue
            condition, then = parts
            if not EQUALITY.search(condition) and not condition.startswith("== "):
                continue
            conds = [v for v in literals(condition) if not trivial(v) and v not in known]
            if not conds:
                continue
            results, text = [v for v in literals(then) if not trivial(v)], [b[j].strip()]
            k = j + 1
            while not results and k < min(j2, j + 4):
                if CONDITIONAL.match(b[k]):
                    break
                text.append(b[k].strip())
                line = strip_comment(b[k])
                if RESULT_LINE.match(line):
                    results = [v for v in literals(line.split("=", 1)[-1] if "return" not in line else line)
                               if not trivial(v)]
                    break
                k += 1
            if results:
                out.append(SpecialCase(j + 1, " ⏎ ".join(t for t in text if t), conds, results))
    return out


def matching_tests(case: SpecialCase, test_literals: dict[str, set[str]]) -> list[str]:
    """Tests that use one of the condition values and one of the result values."""
    return sorted(name for name, values in test_literals.items()
                  if values & set(case.conditions) and values & set(case.results))
