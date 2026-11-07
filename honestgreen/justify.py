"""Justifications as git commit trailers.

    Test-Change: <path>[:<line>] | <finding id or *> | <reason with evidence>

A justification marks a finding as justified: it stays in the report but no
longer fails the check. Reasons that only restate the goal are rejected.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from honestgreen.model import Finding

TRAILER = re.compile(r"^Test-Change:\s*(.+)$", re.MULTILINE)
MIN_REASON_LENGTH = 20
INVALID_REASONS = (
    "test was failing", "tests were failing", "make it pass", "make the test pass",
    "make tests pass", "update test to match implementation", "updated test to match implementation",
    "match implementation", "fix test", "fixed test", "flaky",
)


@dataclass
class Justification:
    path: str
    line: int | None
    finding_id: str
    reason: str
    valid: bool
    problem: str = ""


def _validate(reason: str) -> str:
    low = reason.lower().strip(" .")
    if len(low) < MIN_REASON_LENGTH:
        return f"reason too short (min {MIN_REASON_LENGTH} chars)"
    for bad in INVALID_REASONS:
        if low == bad or low.startswith(bad) and len(low) < len(bad) + 15:
            return f"reason only restates the goal ('{bad}')"
    return ""


def parse(messages: list[str]) -> list[Justification]:
    out = []
    for msg in messages:
        # join indented continuation lines of a trailer
        msg = re.sub(r"\n[ \t]+", " ", msg)
        for m in TRAILER.finditer(msg):
            parts = [p.strip() for p in m.group(1).split("|", 2)]
            if len(parts) < 3:
                out.append(Justification(m.group(1), None, "", "", False,
                                         "expected '<path>[:<line>] | <id> | <reason>'"))
                continue
            loc, fid, reason = parts
            path, _, line = loc.partition(":")
            problem = _validate(reason)
            out.append(Justification(path.strip(), int(line) if line.strip().isdigit() else None,
                                     fid.upper(), reason, not problem, problem))
    return out


def _matches(j: Justification, f: Finding) -> bool:
    if not j.valid:
        return False
    if j.finding_id not in ("*", f.id):
        return False
    if not (f.file == j.path or f.file.endswith("/" + j.path) or j.path.endswith("/" + f.file)):
        return False
    return j.line is None or abs(j.line - f.line) <= 3


def apply(findings: list[Finding], justifications: list[Justification]) -> None:
    for f in findings:
        for j in justifications:
            if _matches(j, f):
                f.justification = j.reason
                break
