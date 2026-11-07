"""Value-level view of a change: literals changed in code, and where the spec mentions them.

Used to catch production code (or the specification itself) being changed to
agree with a test instead of with the specification.
"""
from __future__ import annotations

import difflib
import fnmatch
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

DEFAULT_SPEC_PATTERNS = (
    "README.md", "SPEC.md", "SPECIFICATION.md", "REQUIREMENTS.md",
    "docs/**/*.md", "doc/**/*.md", "spec/**/*.md", "specs/**/*.md", "requirements/**/*.md",
    "**/openapi*.yaml", "**/openapi*.yml", "**/openapi*.json",
    "**/swagger*.yaml", "**/swagger*.yml", "**/swagger*.json",
)

CODE_LITERAL = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|(?<![\w.])\d+(?:\.\d+)?[lLfFdD]?(?![\w.])'
    r"|\b(?:true|false|null|True|False|None)\b")
SPEC_NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![\w])")
WORD = re.compile(r"[A-Za-z][a-z]+|[A-Z]+(?![a-z])")
STOPWORDS = {
    "return", "static", "final", "decimal", "bigdecimal", "self", "this", "public", "private",
    "protected", "const", "class", "import", "value", "values", "string", "none", "null",
    "true", "false", "with", "from", "that", "then", "else", "when", "assert", "equals",
    "test", "tests", "should", "must", "will", "each", "into", "default",
}


def is_spec_file(path: str, patterns=DEFAULT_SPEC_PATTERNS) -> bool:
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(path.rsplit("/", 1)[-1], p)
               for p in patterns)


def words(text: str) -> set[str]:
    """Meaningful lowercase words, splitting camelCase and snake_case."""
    return {w.lower() for w in WORD.findall(text)
            if len(w) >= 4 and w.lower() not in STOPWORDS}


def normalize(literal: str) -> str:
    """Comparable form of a literal: numbers as canonical decimals, strings unquoted."""
    s = literal.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1]
    num = s.rstrip("lLfFdD")
    if re.fullmatch(r"\d+,\d{2}", num):          # 15,00 (pt-BR / EU notation)
        num = num.replace(",", ".")
    try:
        return format(Decimal(num).normalize(), "f")
    except InvalidOperation:
        return s


@dataclass
class ValueChange:
    file: str
    line: int
    old: str        # normalized
    new: str        # normalized
    before: str     # source line before
    after: str      # source line after

    @property
    def context(self) -> set[str]:
        return words(self.before) | words(self.after)


def _literals(line: str, pattern: re.Pattern) -> list[str]:
    return pattern.findall(line)


def value_changes(before_src: str | None, after_src: str | None, path: str,
                  pattern: re.Pattern = CODE_LITERAL) -> list[ValueChange]:
    """Literals that changed on otherwise identical lines (e.g. 15.00 -> 20.00)."""
    if not before_src or not after_src:
        return []
    a, b = before_src.splitlines(), after_src.splitlines()
    out: list[ValueChange] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "replace":
            continue
        used: set[int] = set()
        for i in range(i1, i2):
            best, score = None, 0.0
            for j in range(j1, j2):
                if j in used:
                    continue
                r = difflib.SequenceMatcher(None, a[i], b[j]).ratio()
                if r > score:
                    best, score = j, r
            if best is None or score < 0.6:
                continue
            used.add(best)
            old_line, new_line = a[i], b[best]
            if pattern.sub("§", old_line).strip() != pattern.sub("§", new_line).strip():
                continue
            for old, new in zip(_literals(old_line, pattern), _literals(new_line, pattern)):
                if normalize(old) != normalize(new):
                    out.append(ValueChange(path, best + 1, normalize(old), normalize(new),
                                           old_line.strip(), new_line.strip()))
    return out


@dataclass
class Mention:
    file: str
    line: int
    text: str


def mentions(spec_files: dict[str, str], value: str, context: set[str]) -> list[Mention]:
    """Spec lines that contain `value` and share at least one word with the code context."""
    found = []
    for path, text in spec_files.items():
        for n, line in enumerate(text.splitlines(), 1):
            if not (context & words(line)):
                continue
            values = {normalize(v) for v in SPEC_NUMBER.findall(line)}
            values |= {normalize(t) for t in re.findall(r"[`'\"]([^`'\"]+)[`'\"]", line)}
            values |= {t for t in re.findall(r"\b[A-Z][A-Z0-9_]{3,}\b", line)}
            if value in values:
                found.append(Mention(path, n, line.strip()))
    return found
