"""Extract Jest / Vitest / Mocha / node:test test cases from JavaScript and TypeScript.

No external dependencies: comments, strings, template literals and regular expression
literals are masked first, then `describe` / `it` / `test` calls are matched by their
parentheses. Assertions are `expect(...)` chains, `assert...(...)` calls and chai's
`.should` chains.
"""
from __future__ import annotations

import re

from honestgreen.model import Assertion, TestCase

TEST_FUNCS = {"it", "test", "xit", "xtest", "fit", "ftest"}
SUITE_FUNCS = {"describe", "suite", "context", "xdescribe", "fdescribe"}
SKIP_MODIFIERS = {"skip", "todo", "failing", "skipIf", "runIf"}
SKIP_FUNCS = {"xit", "xtest", "xdescribe"}

STRONG = {"toBe", "toEqual", "toStrictEqual", "toBeCloseTo", "toHaveLength", "toHaveBeenCalledWith",
          "toHaveBeenCalledTimes", "toHaveBeenLastCalledWith", "toHaveBeenNthCalledWith",
          "toHaveReturnedWith", "toMatchInlineSnapshot", "toThrowError",
          "equal", "equals", "eql", "deepEqual", "deepStrictEqual", "strictEqual", "throws", "rejects",
          "notStrictEqual", "notDeepStrictEqual", "members", "lengthOf", "length"}
WEAK = {"toBeTruthy", "toBeFalsy", "toBeDefined", "toBeUndefined", "toBeNull", "toBeNaN",
        "ok", "exist", "true", "false", "null", "undefined", "empty", "doesNotThrow", "ifError"}
VALUE_MATCHERS = {"toThrow"}      # strong with an expected error, relational without

CALL = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)((?:\s*\.\s*[A-Za-z_$][\w$]*)*)\s*\(")
LITERAL = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`'
                     r"|(?<![\w$.])-?\d+(?:\.\d+)?n?(?![\w$])|\b(?:true|false|null|undefined)\b")
REGEX_PREFIX = set("(,=:[!&|?{};+-*%<>~^") | {""}
BODY_SKIP = re.compile(r"(?<![\w$.])(?:(?:this|ctx|context|t)\s*\.\s*skip|pending)\s*\(")
MODIFIERS = SKIP_MODIFIERS | {"only", "each", "concurrent", "sequential"}
TWO_CALLS = {"each", "skipIf", "runIf"}     # it.each(table)("name", fn), test.skipIf(cond)("name", fn)


def _norm(text: str) -> str:
    return " ".join(text.split())


def mask(source: str) -> str:
    """Blank out comments and the contents of strings, templates and regex literals."""
    out = list(source)
    i, n = 0, len(source)

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    def prev_token(k: int) -> str:
        k -= 1
        while k >= 0 and source[k] in " \t\r\n":
            k -= 1
        if k < 0:
            return ""
        if source[k].isalnum() or source[k] in "_$":
            j = k
            while j >= 0 and (source[j].isalnum() or source[j] in "_$"):
                j -= 1
            return source[j + 1:k + 1]
        return source[k]

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
        elif c in "\"'`":
            j = i + 1
            while j < n and source[j] != c and (c == "`" or source[j] != "\n"):
                j += 2 if source[j] == "\\" else 1
            blank(i + 1, min(j, n))
            i = j + 1
        elif c == "/" and (prev_token(i) in REGEX_PREFIX or prev_token(i) in ("return", "typeof", "in", "of")):
            j, in_class = i + 1, False
            while j < n and source[j] != "\n":
                if source[j] == "\\":
                    j += 2
                    continue
                if source[j] == "[":
                    in_class = True
                elif source[j] == "]":
                    in_class = False
                elif source[j] == "/" and not in_class:
                    break
                j += 1
            if j < n and source[j] == "/":
                blank(i + 1, j)
                i = j + 1
            else:
                i += 1
        else:
            i += 1
    return "".join(out)


def _match(masked: str, start: int) -> int:
    """Index of the parenthesis closing the one at `start` (or len-1 if unbalanced)."""
    depth = 0
    for k in range(start, len(masked)):
        if masked[k] == "(":
            depth += 1
        elif masked[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    return len(masked) - 1


def _chain_end(masked: str, k: int) -> int:
    """Extend a call ending at k (exclusive) over `.name`, `.name(...)` and `[...]` links."""
    while True:
        m = re.match(r"\s*\.\s*[A-Za-z_$][\w$]*", masked[k:])
        if not m:
            return k
        k += m.end()
        p = re.match(r"\s*\(", masked[k:])
        if p:
            k = _match(masked, k + p.end() - 1) + 1


def _first_arg_name(source: str, masked: str, open_paren: int) -> str | None:
    """The string literal that opens a call's argument list, unquoted."""
    m = re.match(r"\s*([\"'`])", masked[open_paren + 1:])
    if not m:
        return None
    start = open_paren + 1 + m.end()
    end = masked.find(m.group(1), start)
    return _norm(source[start:end]) if end != -1 else None


def _strength(text: str) -> int:
    links = re.findall(r"\.\s*([A-Za-z_$][\w$]*)", text)
    if text.startswith("assert") and not links:
        return 1                                       # assert(x)
    if "not" in links:
        return 1
    last = links[-1] if links else ""
    if last in VALUE_MATCHERS:
        return 3 if re.search(r"toThrow\s*\(\s*[^)\s]", text) else 2
    if last in STRONG or (len(links) > 1 and links[-2] in STRONG and last not in WEAK):
        return 3
    if last in WEAK:
        return 1
    return 2


def _assertion(text: str, line: int) -> Assertion:
    return Assertion(text=text, skeleton=LITERAL.sub("§", text), literals=tuple(LITERAL.findall(text)),
                     strength=_strength(text), line=line)


def _supertest_strength(args: str) -> int:
    """`.expect(200)`, `.expect("body")` are exact; regexes and callbacks are looser."""
    return 2 if re.search(r"[(,]\s*/|function\b|=>", args) else 3


def _assertions(source: str, masked: str, start: int, end: int) -> list[Assertion]:
    out, k = [], start
    pattern = re.compile(r"(?<![\w$.])(expect|assert)\b|\.\s*should\b|(\.\s*expect\s*\()")
    while True:
        m = pattern.search(masked, k, end)
        if not m:
            return out
        if m.group(2):                                 # supertest: request(app).get("/").expect(200)
            a, b = m.start() + 1, _match(masked, m.end() - 1) + 1
            text = _norm(source[a:b])
            out.append(Assertion(text=text, skeleton=LITERAL.sub("§", text),
                                 literals=tuple(LITERAL.findall(text)),
                                 strength=_supertest_strength(source[m.end() - 1:b]),
                                 line=source.count("\n", 0, a) + 1))
            k = b
            continue
        if m.group(1):
            p = re.match(r"\s*(?:\.\s*[A-Za-z_$][\w$]*\s*)*\(", masked[m.end():end])
            if not p:
                k = m.end()
                continue
            close = _match(masked, m.end() + p.end() - 1)
            a, b = m.start(), _chain_end(masked, close + 1)
        else:                                          # value.should.equal(x)
            a = masked.rfind("\n", 0, m.start()) + 1
            a += len(masked[a:m.start()]) - len(masked[a:m.start()].lstrip())
            b = _chain_end(masked, m.end())
        out.append(_assertion(_norm(source[a:b]), source.count("\n", 0, a) + 1))
        k = b


def parse(source: str, path: str) -> dict[str, TestCase]:
    masked = mask(source)
    suites: list[tuple[int, int, str, set[str]]] = []      # (start, end, name, skips)
    calls = []
    for m in CALL.finditer(masked):
        base, links = m.group(1), [x.strip() for x in m.group(2).split(".") if x.strip()]
        if base not in TEST_FUNCS | SUITE_FUNCS or any(link not in MODIFIERS for link in links):
            continue
        open_paren = m.end() - 1
        skips = set()
        if base in SKIP_FUNCS:
            skips.add(base)
        for link in links:
            if link in SKIP_MODIFIERS:
                skips.add(f"{base}.{link}")
        if TWO_CALLS & set(links):
            first_close = _match(masked, open_paren)
            nxt = re.match(r"\s*\(", masked[first_close + 1:])
            if not nxt:
                continue
            open_paren = first_close + nxt.end()
        name = _first_arg_name(source, masked, open_paren)
        if name is None:
            continue
        close = _match(masked, open_paren)
        if base in SUITE_FUNCS:
            suites.append((open_paren, close, name, skips))
        else:
            calls.append((m.start(), open_paren, close, name, skips, base, links))

    tests: dict[str, TestCase] = {}
    for start, open_paren, close, name, skips, base, links in calls:
        enclosing = sorted((s for s in suites if s[0] < start < s[1]), key=lambda s: s[0])
        full = " > ".join([s[2] for s in enclosing] + [name])
        if full in tests:
            n = 2
            while f"{full} #{n}" in tests:
                n += 1
            full = f"{full} #{n}"
        inherited = set().union(*(s[3] for s in enclosing)) if enclosing else set()
        body_skips = set()   # this.skip() (Mocha), ctx.skip() (Vitest), t.skip() (node:test), pending()
        for b in BODY_SKIP.finditer(masked, open_paren, close):
            body_skips.add(_norm(source[b.start():_match(masked, b.end() - 1) + 1]))
        tests[full] = TestCase(
            name=full, file=path, line=source.count("\n", 0, start) + 1,
            source=_norm(source[start:close + 1]),
            assertions=_assertions(source, masked, open_paren, close),
            skip_markers=skips | inherited | body_skips,
        )
    return tests
