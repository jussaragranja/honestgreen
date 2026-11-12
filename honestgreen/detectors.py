"""Detectors: compare the tests of one file before and after a change.

HG001  Assertion removed
HG002  Test disabled (skip/xfail/@Disabled/@Ignore/assumptions added)
HG003  Assertion weakened (replaced by a less strict check)
HG004  Assertion modified (expected value or inputs changed)
HG005  Test deleted or renamed
"""
from __future__ import annotations

import difflib
from collections import Counter

from honestgreen.model import Assertion, Finding, TestCase
from honestgreen.parsers import parse

TITLES = {
    "HG001": "Assertion removed",
    "HG002": "Test disabled",
    "HG003": "Assertion weakened",
    "HG004": "Assertion modified",
    "HG005": "Test deleted or renamed",
    "HG006": "Production code special-cased for a test",
    "HG010": "Integrity policy changed",
    "HG011": "Protected test modified",
    "HG020": "Code contradicts specification",
    "HG021": "Specification changed",
    "HG030": "Change not disclosed in summary",
}

RENAME_SIMILARITY = 0.5
PAIR_SIMILARITY = 0.4


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _body_without_name(test: TestCase) -> str:
    short = test.name.rsplit(".", 1)[-1]
    return test.source.replace(short, "§name§")


def _multiset_diff(before: list[Assertion], after: list[Assertion]):
    remaining = Counter(a.text for a in after)
    removed = []
    for a in before:
        if remaining[a.text] > 0:
            remaining[a.text] -= 1
        else:
            removed.append(a)
    still = Counter(a.text for a in before)
    added = []
    for a in after:
        if still[a.text] > 0:
            still[a.text] -= 1
        else:
            added.append(a)
    return removed, added


def compare_tests(before: TestCase, after: TestCase, production_changed: bool,
                  renamed_from: str | None = None) -> list[Finding]:
    findings: list[Finding] = []
    label = f"{after.name} (renamed from {renamed_from})" if renamed_from else after.name

    def add(id_: str, severity: str, message: str, b: str = "", a: str = "", line: int = 0) -> None:
        findings.append(Finding(id=id_, title=TITLES[id_], severity=severity, file=after.file,
                                line=line or after.line, test=label, message=message,
                                before=b, after=a))

    new_skips = sorted(after.skip_markers - before.skip_markers)
    if new_skips:
        add("HG002", "high", "Test was disabled: " + "; ".join(new_skips),
            a="; ".join(new_skips))

    removed, added = _multiset_diff(before.assertions, after.assertions)

    # 1. same shape, different literals -> expected value (or input) changed
    for r in list(removed):
        match = next((a for a in added if a.skeleton == r.skeleton), None)
        if match:
            removed.remove(r)
            added.remove(match)
            severity = "high" if production_changed else "medium"
            add("HG004", severity,
                "Literal values in an assertion changed"
                + (" in the same change as production code." if production_changed else "."),
                r.text, match.text, match.line)

    # 2. pair remaining by similarity -> weakened or modified
    for r in list(removed):
        best = max(added, key=lambda a: _ratio(a.text, r.text), default=None)
        if best is None or _ratio(best.text, r.text) < PAIR_SIMILARITY:
            continue
        removed.remove(r)
        added.remove(best)
        if best.strength < r.strength:
            add("HG003", "medium", "Assertion replaced by a less strict check.",
                r.text, best.text, best.line)
        else:
            add("HG004", "medium", "Assertion changed (inputs or structure).",
                r.text, best.text, best.line)

    # 3. anything left was removed outright
    for r in removed:
        add("HG001", "high", "Assertion removed and not replaced.", r.text, "", r.line)
    return findings


def compare_file(before_src: str | None, after_src: str | None, before_path: str,
                 after_path: str, production_changed: bool) -> tuple[list[Finding], dict, dict]:
    """Return (findings, before tests, after tests) for one test file."""
    before = parse(before_src, before_path) if before_src is not None else {}
    after = parse(after_src, after_path) if after_src is not None else {}
    findings: list[Finding] = []

    gone = [n for n in before if n not in after]
    new = [n for n in after if n not in before]
    renames: dict[str, str] = {}
    for old in gone:
        candidates = [(n, _ratio(_body_without_name(before[old]), _body_without_name(after[n])))
                      for n in new if n not in renames.values()]
        best = max(candidates, key=lambda c: c[1], default=None)
        if best and best[1] >= RENAME_SIMILARITY:
            renames[old] = best[0]

    for name, b in before.items():
        if name in after:
            findings += compare_tests(b, after[name], production_changed)
        elif name in renames:
            a = after[renames[name]]
            findings.append(Finding(
                id="HG005", title=TITLES["HG005"], severity="low", file=after_path,
                line=a.line, test=a.name, message=f"Test renamed from {name}.",
                before=name, after=a.name))
            findings += compare_tests(b, a, production_changed, renamed_from=name)
        else:
            where = after_path if after_src is not None else before_path
            findings.append(Finding(
                id="HG005", title=TITLES["HG005"], severity="high", file=where,
                line=b.line, test=name,
                message="Test deleted" + (" (file removed)." if after_src is None else "."),
                before=b.source[:300]))
    return findings, before, after
