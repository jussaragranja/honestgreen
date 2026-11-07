"""Run all checks over the changes between a base ref and HEAD (or the working tree).

Two questions are answered:
  1. Were the tests weakened?                      (HG001-HG005, HG010, HG011)
  2. Is the source of truth still the source of truth?
       - production values that now contradict the spec (HG020)
       - the spec itself changed, possibly to match the code (HG021)
       - the author's summary hides what was done (HG030, with --claims)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from honestgreen import claims as claims_mod
from honestgreen import gitio, justify
from honestgreen.detectors import TITLES, compare_file
from honestgreen.model import Finding, severity_rank
from honestgreen.parsers import is_test_file, language, parse
from honestgreen.policy import POLICY_FILE, Policy
from honestgreen.values import SPEC_NUMBER, Mention, ValueChange, is_spec_file, mentions, normalize, value_changes

DOC_SUFFIXES = (".md", ".txt", ".rst", ".adoc")


@dataclass
class FileChange:
    path: str
    kind: str        # production | test | spec | policy | other
    status: str      # A M D R
    added: int
    removed: int


@dataclass
class ValueReport:
    change: ValueChange
    status: str      # contradicts | spec_changed | aligned | unspecified
    spec: list[Mention] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)   # tests whose assertions use the new value


@dataclass
class Result:
    base: str
    base_commit: str
    head: str
    findings: list[Finding] = field(default_factory=list)
    rejected_justifications: list[justify.Justification] = field(default_factory=list)
    files: list[FileChange] = field(default_factory=list)
    values: list[ValueReport] = field(default_factory=list)
    claims_checked: bool = False
    spec_files: list[str] = field(default_factory=list)
    fail_on: str = "high"

    @property
    def files_checked(self) -> int:
        return sum(1 for f in self.files if f.kind == "test")

    @property
    def blocking(self) -> list[Finding]:
        if self.fail_on == "never":
            return []
        limit = severity_rank(self.fail_on)
        return [f for f in self.findings if not f.justified and severity_rank(f.severity) >= limit]

    @property
    def failed(self) -> bool:
        return bool(self.blocking)

    def summary(self) -> dict:
        out = {"high": 0, "medium": 0, "low": 0, "justified": 0}
        for f in self.findings:
            out["justified" if f.justified else f.severity] += 1
        return out


def classify(path: str, policy: Policy) -> str:
    if path == POLICY_FILE:
        return "policy"
    if is_test_file(path, policy.test_patterns):
        return "test"
    if is_spec_file(path, policy.spec_patterns):
        return "spec"
    if path.endswith(DOC_SUFFIXES):
        return "other"
    return "production"


def _test_expectations(repo: Path, head: str | None, policy: Policy, base_commit: str) -> dict[str, set[str]]:
    """{normalized literal: {test names}} over the head version of all test files."""
    paths = gitio.files_at(repo, head or "HEAD") if head else [
        p for p in gitio.files_at(repo, base_commit)] + [
        c.new_path for c in gitio.changes(repo, base_commit, None) if c.new_path]
    out: dict[str, set[str]] = {}
    for path in sorted(set(paths)):
        if not is_test_file(path, policy.test_patterns):
            continue
        src = gitio.read_head(repo, head, path)
        if not src:
            continue
        for test in parse(src, path).values():
            for a in test.assertions:
                for lit in a.literals:
                    out.setdefault(normalize(str(lit)), set()).add(test.name)
    return out


def run(repo: Path, base: str, head: str | None, policy: Policy,
        claims_text: str | None = None) -> Result:
    head_ref = head or "HEAD"
    base_commit = gitio.merge_base(repo, base, head_ref)
    changes = gitio.changes(repo, base_commit, head)
    stats = gitio.numstat(repo, base_commit, head)
    result = Result(base=base, base_commit=base_commit, head=head or "working tree",
                    fail_on=policy.fail_on)

    for c in changes:
        path = c.new_path or c.old_path
        added, removed = stats.get(path, (0, 0))
        result.files.append(FileChange(path, classify(path, policy), c.status, added, removed))
    production_changed = any(f.kind == "production" for f in result.files)

    # ------------------------------------------------------------ 1. tests
    for c in changes:
        path = c.new_path or c.old_path
        if path == POLICY_FILE:
            action = {"A": "added", "D": "deleted"}.get(c.status, "changed")
            result.findings.append(Finding(
                id="HG010", title=TITLES["HG010"], severity="high", file=POLICY_FILE, line=1,
                test="", message=f"The test integrity policy was {action} in this change. "
                                 "It only takes effect after merge; this check used the base policy."))
            continue
        if not any(p and is_test_file(p, policy.test_patterns) for p in (c.old_path, c.new_path)):
            continue
        if not any(language(p) for p in (c.old_path, c.new_path) if p):
            continue
        before_src = gitio.read_at(repo, base_commit, c.old_path) if c.old_path else None
        after_src = gitio.read_head(repo, head, c.new_path) if c.new_path else None
        if before_src == after_src:
            continue
        findings, before_tests, after_tests = compare_file(
            before_src, after_src, c.old_path or c.new_path, c.new_path or c.old_path,
            production_changed)

        protected = policy.is_protected(c.old_path or "") or policy.is_protected(c.new_path or "")
        if protected:
            flagged = {f.test.split(" (renamed")[0] for f in findings}
            for name, b in before_tests.items():
                a = after_tests.get(name)
                if a is not None and a.source != b.source and name not in flagged:
                    findings.append(Finding(
                        id="HG011", title=TITLES["HG011"], severity="high", file=a.file,
                        line=a.line, test=name, message="A protected test was modified."))
        for f in findings:
            if protected:
                f.protected = True
            result.findings.append(f)

    # ------------------------------------------------------------ 2. source of truth
    base_spec_paths = [p for p in gitio.files_at(repo, base_commit) if is_spec_file(p, policy.spec_patterns)]
    head_spec_paths = set(base_spec_paths) | {
        f.path for f in result.files if f.kind == "spec" and f.status != "D"}
    base_spec = {p: gitio.read_at(repo, base_commit, p) or "" for p in base_spec_paths}
    head_spec = {p: gitio.read_head(repo, head, p) or "" for p in sorted(head_spec_paths)}
    result.spec_files = sorted(head_spec_paths)

    if result.spec_files:
        expectations = _test_expectations(repo, head, policy, base_commit)
        handled_spec_lines: set[tuple[str, int]] = set()
        for c in changes:
            path = c.new_path or c.old_path
            if classify(path, policy) != "production" or not c.old_path or not c.new_path:
                continue
            before_src = gitio.read_at(repo, base_commit, c.old_path)
            after_src = gitio.read_head(repo, head, c.new_path)
            for vc in value_changes(before_src, after_src, path):
                ctx = vc.context
                old_base = mentions(base_spec, vc.old, ctx)
                old_head = mentions(head_spec, vc.old, ctx)
                new_head = mentions(head_spec, vc.new, ctx)
                tests = sorted(expectations.get(vc.new, set()))
                if old_base and old_head and not new_head:
                    report = ValueReport(vc, "contradicts", old_head, tests)
                    m = old_head[0]
                    evidence = f" The new value matches the expectation in {', '.join(tests[:3])}." if tests else ""
                    result.findings.append(Finding(
                        id="HG020", title=TITLES["HG020"], severity="high", file=path,
                        line=vc.line, test="",
                        message=f"{vc.old} → {vc.new}, but {m.file}:{m.line} says: “{m.text}”.{evidence}",
                        before=vc.before, after=vc.after))
                elif old_base and new_head and not old_head:
                    report = ValueReport(vc, "spec_changed", new_head, tests)
                    for m in new_head:
                        handled_spec_lines.add((m.file, m.line))
                        result.findings.append(Finding(
                            id="HG021", title=TITLES["HG021"], severity="high", file=m.file,
                            line=m.line, test="",
                            message=f"The specification was changed from {vc.old} to {vc.new} together with "
                                    f"the code ({path}:{vc.line}). Confirm the requirement really changed.",
                            before=vc.old, after=m.text))
                elif new_head:
                    report = ValueReport(vc, "aligned", new_head, tests)
                else:
                    report = ValueReport(vc, "unspecified", [], tests)
                result.values.append(report)

        for f in result.files:
            if f.kind != "spec" or f.status in ("A", "D"):
                continue
            for vc in value_changes(base_spec.get(f.path), head_spec.get(f.path), f.path, SPEC_NUMBER):
                line_in_head = vc.line
                if (f.path, line_in_head) in handled_spec_lines:
                    continue
                matches = sorted(expectations.get(vc.new, set()))
                result.findings.append(Finding(
                    id="HG021", title=TITLES["HG021"], severity="high" if matches else "medium",
                    file=f.path, line=line_in_head, test="",
                    message=f"A value in the specification changed: {vc.old} → {vc.new}."
                            + (f" The new value matches the expectation in {', '.join(matches[:3])}."
                               if matches else ""),
                    before=vc.before, after=vc.after))

    # ------------------------------------------------------------ policy, justification, claims
    kept = []
    for f in result.findings:
        if f.id != "HG010" and not policy.enabled(f.id):
            continue
        if f.id != "HG010":
            f.severity = policy.severity_for(f.id, f.severity)
        if f.protected:
            f.severity = "high"
        kept.append(f)
    result.findings = kept

    trailers = justify.parse(gitio.commit_messages(repo, base_commit, head))
    justify.apply(result.findings, trailers)
    result.rejected_justifications = [j for j in trailers if not j.valid]

    if claims_text is not None:
        result.claims_checked = True
        extra = [f for f in claims_mod.check(result.findings, claims_text) if policy.enabled(f.id)]
        for f in extra:
            f.severity = policy.severity_for(f.id, f.severity)
        result.findings += extra

    result.findings.sort(key=lambda f: (-severity_rank(f.severity), f.file, f.line))
    return result
