"""Extract JUnit 4/5 test methods from Java source without external dependencies.

Comments and string literals are masked first, so braces, parentheses and
annotations inside them never confuse the structural scan.
"""
from __future__ import annotations

import re

from honestgreen.model import Assertion, TestCase

TEST_ANNOTATIONS = {"Test", "ParameterizedTest", "RepeatedTest", "TestFactory", "TestTemplate"}
SKIP_ANNOTATIONS = {"Disabled", "Ignore", "DisabledIf", "DisabledOnOs", "DisabledIfSystemProperty",
                    "DisabledIfEnvironmentVariable"}
STRONG = {"assertEquals", "assertArrayEquals", "assertIterableEquals", "assertLinesMatch",
          "assertSame", "assertNotSame", "assertThrows", "assertThrowsExactly", "assertNotEquals",
          "assertAll"}
WEAK = {"assertNotNull", "assertNull", "assertTrue", "assertFalse", "assertDoesNotThrow"}
ASSERTJ_STRONG = {"isEqualTo", "containsExactly", "containsExactlyInAnyOrder", "isSameAs",
                  "hasMessage", "isEqualByComparingTo", "hasSize", "isInstanceOf", "isExactlyInstanceOf"}
ASSERTJ_WEAK = {"isNotNull", "isNull", "isTrue", "isFalse", "isNotEmpty", "isEmpty", "isNotBlank"}

ASSERT_CALL = re.compile(r"(?:\b[\w.]+\.)?\b(assert\w*|fail|verify)\s*\(")
ASSUME_CALL = re.compile(r"(?:\b[\w.]+\.)?\b(assume\w*)\s*\(")
CLASS_DECL = re.compile(r"\b(class|interface|enum|record)\s+(\w+)")
LITERAL = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])+\'|\b\d+(?:\.\d+)?[lLfFdD]?\b|\b(?:true|false|null)\b')


def _norm(text: str) -> str:
    return " ".join(text.split())


def mask(source: str) -> str:
    """Blank out comments and the contents of string/char literals, keeping offsets."""
    out = list(source)
    i, n = 0, len(source)

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = source[i]
        if source.startswith("//", i):
            j = source.find("\n", i)
            j = n if j == -1 else j
            blank(i, j)
            i = j
        elif source.startswith("/*", i):
            j = source.find("*/", i + 2)
            j = n if j == -1 else j + 2
            blank(i, j)
            i = j
        elif source.startswith('"""', i):
            j = source.find('"""', i + 3)
            j = n if j == -1 else j + 3
            blank(i + 3, max(i + 3, j - 3))
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and source[j] != c and source[j] != "\n":
                j += 2 if source[j] == "\\" else 1
            blank(i + 1, min(j, n))
            i = j + 1
        else:
            i += 1
    return "".join(out)


def _match(masked: str, start: int, open_ch: str, close_ch: str) -> int:
    """Index of the bracket closing the one at `start` (or len-1 if unbalanced)."""
    depth = 0
    for k in range(start, len(masked)):
        if masked[k] == open_ch:
            depth += 1
        elif masked[k] == close_ch:
            depth -= 1
            if depth == 0:
                return k
    return len(masked) - 1


def _boundary_before(masked: str, pos: int) -> int:
    k = pos - 1
    while k >= 0 and masked[k] not in ";{}":
        k -= 1
    return k + 1


def _annotations(source: str, masked: str, start: int, end: int) -> list[tuple[str, str]]:
    """(name, full text) of annotations in [start, end)."""
    found = []
    k = start
    while k < end:
        if masked[k] == "@":
            m = re.match(r"@([\w.]+)", masked[k:end])
            if not m:
                k += 1
                continue
            name = m.group(1).rsplit(".", 1)[-1]
            j = k + m.end()
            while j < end and masked[j] in " \t\r\n":
                j += 1
            if j < end and masked[j] == "(":
                j = _match(masked, j, "(", ")") + 1
            found.append((name, _norm(source[k:j])))
            k = j
        else:
            k += 1
    return found


def _strength(name: str, text: str) -> int:
    if name in STRONG:
        return 3
    if name in WEAK:
        if name in ("assertTrue", "assertFalse") and ("==" in text or ".equals(" in text):
            return 2
        return 1
    if name == "assertThat":
        chained = re.findall(r"\.\s*(\w+)\s*\(", text)
        if any(c in ASSERTJ_STRONG for c in chained):
            return 3
        if chained and all(c in ASSERTJ_WEAK for c in chained):
            return 1
        return 2
    return 2  # fail(), verify(), other assert*


def _assertion(text: str, name: str, line: int) -> Assertion:
    literals = tuple(LITERAL.findall(text))
    skeleton = LITERAL.sub("§", text)
    return Assertion(text=text, skeleton=skeleton, literals=literals,
                     strength=_strength(name, text), line=line)


def parse(source: str, path: str) -> dict[str, TestCase]:
    masked = mask(source)
    classes = []  # (start, end, name, skip markers)
    for m in CLASS_DECL.finditer(masked):
        brace = masked.find("{", m.end())
        if brace == -1:
            continue
        end = _match(masked, brace, "{", "}")
        start = _boundary_before(masked, m.start())
        skips = {text for name, text in _annotations(source, masked, start, m.start())
                 if name in SKIP_ANNOTATIONS}
        classes.append((brace, end, m.group(2), skips))

    tests: dict[str, TestCase] = {}
    seen_methods: set[int] = set()
    for m in re.finditer(r"@(\w+)\b", masked):
        if m.group(1) not in TEST_ANNOTATIONS:
            continue
        block_start = _boundary_before(masked, m.start())
        # skip over the annotations (and their arguments) to reach the method signature
        k = block_start
        while True:
            anns_end = k
            sub = re.match(r"\s*@[\w.]+\s*", masked[k:])
            if not sub:
                break
            k += sub.end()
            if k < len(masked) and masked[k] == "(":
                k = _match(masked, k, "(", ")") + 1
            anns_end = k
        paren = masked.find("(", anns_end)
        if paren == -1:
            continue
        name_match = re.search(r"(\w+)\s*$", masked[anns_end:paren])
        if not name_match or paren in seen_methods:
            continue
        seen_methods.add(paren)
        method = name_match.group(1)
        body_open = masked.find("{", _match(masked, paren, "(", ")"))
        if body_open == -1:
            continue
        body_close = _match(masked, body_open, "{", "}")

        enclosing = [c for c in classes if c[0] < m.start() < c[1]]
        owner = max(enclosing, key=lambda c: c[0]) if enclosing else None
        class_skips = set().union(*(c[3] for c in enclosing)) if enclosing else set()
        method_skips = {text for name, text in _annotations(source, masked, block_start, anns_end)
                        if name in SKIP_ANNOTATIONS}

        body_masked = masked[body_open:body_close + 1]
        assertions, assumes = [], set()
        for call in ASSERT_CALL.finditer(body_masked):
            stmt_end = body_masked.find(";", call.end())
            stmt_end = len(body_masked) if stmt_end == -1 else stmt_end
            a, b = body_open + call.start(), body_open + stmt_end
            line = source.count("\n", 0, a) + 1
            assertions.append(_assertion(_norm(source[a:b]), call.group(1), line))
        for call in ASSUME_CALL.finditer(body_masked):
            close = _match(body_masked, body_masked.find("(", call.start()), "(", ")")
            assumes.add(_norm(source[body_open + call.start():body_open + close + 1]))

        full = f"{owner[2]}.{method}" if owner else method
        tests[full] = TestCase(
            name=full, file=path, line=source.count("\n", 0, paren) + 1,
            source=_norm(source[block_start:body_close + 1]), assertions=assertions,
            skip_markers=class_skips | method_skips | assumes,
        )
    return tests
