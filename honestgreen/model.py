"""Data model shared by parsers, detectors and reporters."""
from __future__ import annotations

from dataclasses import dataclass, field

SEVERITIES = ("low", "medium", "high")


def severity_rank(severity: str) -> int:
    return SEVERITIES.index(severity) if severity in SEVERITIES else -1


@dataclass(frozen=True)
class Assertion:
    """One verification inside a test."""

    text: str          # normalized source of the assertion statement
    skeleton: str      # text with literals replaced, used to spot changed expected values
    literals: tuple    # literal values, in order
    strength: int      # 3 exact (equality, raises), 2 relational, 1 weak (truthiness, not-null)
    line: int


@dataclass
class TestCase:
    name: str                      # "Class.method" or "function"
    file: str
    line: int
    source: str                    # whitespace-normalized source of the test
    assertions: list[Assertion] = field(default_factory=list)
    skip_markers: set[str] = field(default_factory=set)  # includes class/module-level markers


@dataclass
class Finding:
    id: str
    title: str
    severity: str
    file: str
    line: int
    test: str
    message: str
    before: str = ""
    after: str = ""
    protected: bool = False
    justification: str | None = None
    disclosure: str | None = None   # explicit | understated | undisclosed (only with --claims)

    @property
    def justified(self) -> bool:
        return self.justification is not None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "severity": self.severity,
            "file": self.file, "line": self.line, "test": self.test,
            "message": self.message, "before": self.before, "after": self.after,
            "protected": self.protected, "justification": self.justification,
            "disclosure": self.disclosure,
        }
