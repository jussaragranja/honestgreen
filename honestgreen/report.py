"""Reports: text (terminal), md (pull request / final report), json (agents), sarif (code scanning).

The text and markdown reports answer, in order:
  1. Verdict: can this be merged?
  2. What changed: production code, tests, specification
  3. Values changed in production code, checked against the specification
  4. Findings
  5. Summary check: did the author say what they did? (with --claims)
  6. Justifications
"""
from __future__ import annotations

import json

from honestgreen import __version__
from honestgreen.detectors import TITLES
from honestgreen.engine import Result

ICON = {"high": "🔴", "medium": "🟡", "low": "⚪"}
KIND_LABEL = {"production": "Production code", "test": "Tests", "spec": "Specification",
              "policy": "Integrity policy", "other": "Other"}
STATUS_LABEL = {
    "contradicts": "❌ contradicts the specification",
    "spec_changed": "⚠️ specification changed to the new value",
    "aligned": "✅ matches the specification",
    "unspecified": "— not in the specification",
}
DISCLOSURE_LABEL = {"explicit": "✅ described", "understated": "⚠️ understated",
                    "undisclosed": "❌ not mentioned"}


def _verdict(r: Result) -> tuple[str, str]:
    s = r.summary()
    if r.failed:
        return "❌", f"Blocked: {len(r.blocking)} unjustified finding(s) at or above “{r.fail_on}”."
    if r.findings:
        return "⚠️", f"Not blocking, but review {s['high'] + s['medium'] + s['low']} finding(s)" + (
            f" ({s['justified']} justified)." if s["justified"] else ".")
    return "✅", "No test integrity findings."


def _kind_totals(r: Result) -> list[tuple[str, int, int, int]]:
    out = []
    for kind in ("production", "test", "spec", "policy", "other"):
        files = [f for f in r.files if f.kind == kind]
        if files:
            out.append((kind, len(files), sum(f.added for f in files), sum(f.removed for f in files)))
    return out


def _disclosure_rows(r: Result):
    return [f for f in r.findings if f.disclosure is not None]


# ---------------------------------------------------------------- json

def to_json(r: Result) -> str:
    return json.dumps({
        "version": "2",
        "tool": f"honestgreen {__version__}",
        "base": r.base, "base_commit": r.base_commit, "head": r.head,
        "fail_on": r.fail_on, "failed": r.failed, "summary": r.summary(),
        "files": [vars(f) for f in r.files],
        "values": [{"file": v.change.file, "line": v.change.line, "old": v.change.old,
                    "new": v.change.new, "status": v.status,
                    "spec": [vars(m) for m in v.spec], "tests_expecting_new_value": v.tests}
                   for v in r.values],
        "spec_files": r.spec_files,
        "claims_checked": r.claims_checked,
        "findings": [f.to_dict() for f in r.findings],
        "rejected_justifications": [
            {"path": j.path, "finding_id": j.finding_id, "reason": j.reason, "problem": j.problem}
            for j in r.rejected_justifications],
    }, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------- text

def to_text(r: Result) -> str:
    icon, verdict = _verdict(r)
    out = [f"Honest Green report · {r.base} → {r.head}", "", f"{icon} {verdict}", ""]

    out.append("What changed")
    if not r.files:
        out.append("  nothing")
    for kind, n, add, rem in _kind_totals(r):
        out.append(f"  {KIND_LABEL[kind]:<17} {n} file(s)  +{add} −{rem}")
        for f in [x for x in r.files if x.kind == kind][:12]:
            out.append(f"      {f.status} {f.path}")

    if r.values:
        out += ["", "Values changed in production code"]
        for v in r.values:
            where = f"  ({v.spec[0].file}:{v.spec[0].line})" if v.spec else ""
            out.append(f"  {v.change.file}:{v.change.line}  {v.change.old} → {v.change.new}  "
                       f"{STATUS_LABEL[v.status]}{where}")

    out += ["", "Findings" if r.findings else "Findings: none"]
    for f in r.findings:
        tag = "justified" if f.justified else f.severity.upper()
        out.append(f"\n  [{tag}] {f.id} {f.title} — {f.file}:{f.line}")
        if f.test:
            out.append(f"      test:   {f.test}")
        out.append(f"      {f.message}")
        if f.before:
            out.append(f"      before: {f.before[:160]}")
        if f.after:
            out.append(f"      after:  {f.after[:160]}")
        if f.justified:
            out.append(f"      justification: {f.justification}")

    if r.claims_checked:
        rows = _disclosure_rows(r)
        out += ["", "Summary check (what was said vs what was done)"]
        if not rows:
            out.append("  nothing to check")
        for f in rows:
            out.append(f"  {DISCLOSURE_LABEL[f.disclosure]:<17} {f.id} {f.title}"
                       + (f" · {f.test}" if f.test else f" · {f.file}:{f.line}"))

    for j in r.rejected_justifications:
        out.append(f"\n⚠ Rejected Test-Change trailer for {j.path}: {j.problem}")
    s = r.summary()
    out.append(f"\n{s['high']} high · {s['medium']} medium · {s['low']} low · {s['justified']} justified"
               f" · fail_on={r.fail_on} · {'FAILED' if r.failed else 'passed'}")
    return "\n".join(out)


# ---------------------------------------------------------------- markdown

def _cell(text: str | None, limit: int = 90) -> str:
    if not text:
        return ""
    text = text.replace("|", "\\|").replace("\n", " ")
    return f"`{text[:limit]}{'…' if len(text) > limit else ''}`"


def to_markdown(r: Result) -> str:
    icon, verdict = _verdict(r)
    out = ["<!-- honestgreen -->", "## Honest Green report", "",
           f"{icon} **{verdict}**", "", f"`{r.base}` → `{r.head}`", ""]

    out += ["### What changed", ""]
    if r.files:
        out += ["| Area | Files | Lines |", "|---|---|---|"]
        for kind, n, add, rem in _kind_totals(r):
            out.append(f"| {KIND_LABEL[kind]} | {n} | +{add} −{rem} |")
        out += ["", "<details><summary>Files</summary>", ""]
        out += [f"- `{f.status}` {f.path} ({KIND_LABEL[f.kind].lower()})" for f in r.files]
        out += ["", "</details>"]
    else:
        out.append("Nothing.")

    if r.values:
        out += ["", "### Values changed in production code", "",
                "| Location | Change | Specification |", "|---|---|---|"]
        for v in r.values:
            spec = f"{STATUS_LABEL[v.status]}" + (
                f": `{v.spec[0].file}:{v.spec[0].line}` {_cell(v.spec[0].text, 70)}" if v.spec else "")
            out.append(f"| `{v.change.file}:{v.change.line}` | `{v.change.old}` → `{v.change.new}` | {spec} |")

    out += ["", "### Findings", ""]
    if r.findings:
        out += ["| | Finding | Location | Detail | Before → After | Justification |",
                "|---|---|---|---|---|---|"]
        for f in r.findings:
            change = " → ".join(x for x in (_cell(f.before, 60), _cell(f.after, 60)) if x)
            detail = (f"{_cell(f.test, 50)} " if f.test else "") + f.message.replace("|", "\\|")[:160]
            just = f"✅ {_cell(f.justification, 80)}" if f.justified else "—"
            out.append(f"| {ICON[f.severity]} | **{f.id}** {f.title} | `{f.file}:{f.line}` | "
                       f"{detail} | {change} | {just} |")
    else:
        out.append("None.")

    if r.claims_checked:
        out += ["", "### Summary check: what was said vs what was done", ""]
        rows = _disclosure_rows(r)
        if rows:
            out += ["| Change | In the summary |", "|---|---|"]
            for f in rows:
                what = f"**{f.id}** {f.title}" + (f" · {_cell(f.test, 50)}" if f.test else f" · `{f.file}:{f.line}`")
                out.append(f"| {what} | {DISCLOSURE_LABEL[f.disclosure]} |")
        else:
            out.append("Nothing to check.")

    if r.findings and not all(f.justified for f in r.findings):
        out += ["", "<details><summary>How to justify a legitimate change</summary>", "",
                "Add a trailer to the commit message:", "", "```",
                "Test-Change: <file>[:<line>] | <finding id> | <why, with evidence>", "```", "</details>"]
    for j in r.rejected_justifications:
        out.append(f"\n⚠️ Rejected `Test-Change` trailer for `{j.path}`: {j.problem}")
    s = r.summary()
    out += ["", f"<sub>{s['high']} high · {s['medium']} medium · {s['low']} low · {s['justified']} justified · "
                f"fail_on={r.fail_on} · honestgreen {__version__}</sub>"]
    return "\n".join(out)


# ---------------------------------------------------------------- sarif

def to_sarif(r: Result) -> str:
    level = {"high": "error", "medium": "warning", "low": "note"}
    rules = [{"id": k, "name": v.replace(" ", ""), "shortDescription": {"text": v}}
             for k, v in TITLES.items()]
    results = []
    for f in r.findings:
        msg = f"{f.title}: {f.message}" + (f" Test: {f.test}." if f.test else "")
        if f.justified:
            msg += f" Justified: {f.justification}"
        results.append({
            "ruleId": f.id,
            "level": "note" if f.justified else level[f.severity],
            "message": {"text": msg},
            "locations": [{"physicalLocation": {
                "artifactLocation": {"uri": f.file},
                "region": {"startLine": max(f.line, 1)}}}],
        })
    return json.dumps({
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "honestgreen", "version": __version__,
                                      "rules": rules}},
                  "results": results}],
    }, indent=2)


FORMATS = {"text": to_text, "json": to_json, "md": to_markdown, "sarif": to_sarif}
