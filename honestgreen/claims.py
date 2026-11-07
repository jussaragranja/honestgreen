"""Compare what the agent (or PR author) said with what the change actually did.

Given a summary text (an agent's final message or a PR description), each
finding is classified as:
  explicit      a sentence names the test/value AND describes the right action
  understated   the test/value is mentioned, but the action is not (e.g. "updated" for a deleted test)
  undisclosed   not mentioned at all
"""
from __future__ import annotations

import re

from honestgreen.model import Finding
from honestgreen.values import SPEC_NUMBER, normalize, words

ACTION_WORDS = {
    "HG001": r"remov|delet|drop",
    "HG002": r"skip|disabl|xfail|ignor|turned off|marked .*skip",
    "HG003": r"weaken|loosen|relax|less strict|replac",
    "HG004": r"chang|updat|correct|align|adjust|modif|edit|rewr|expect",
    "HG005": r"delet|remov|drop|renam|replac",
    "HG010": r"polic",
    "HG011": r"chang|updat|modif|edit",
    "HG020": r"spec|readme|document|conflict|contradict|instead of|mismatch|followed the test|match the test",
    "HG021": r"readme|spec|document",
}
CHECKED = set(ACTION_WORDS)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+|\s+[-*•]\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _subject_terms(f: Finding) -> tuple[set[str], set[str]]:
    """(exact tokens, words) that identify what the finding is about."""
    exact: set[str] = set()
    test = f.test.split(" (renamed")[0]
    if test:
        short = test.rsplit(".", 1)[-1]
        exact |= {short, test}
    stem = re.sub(r"\.\w+$", "", f.file.rsplit("/", 1)[-1])
    exact.add(stem)
    wset = words(stem) | words(test)
    wset -= {"test", "tests"}
    return {e.lower() for e in exact if e}, wset


def _values(f: Finding) -> set[str]:
    return {normalize(v) for v in SPEC_NUMBER.findall(f"{f.before} {f.after}")}


CONFLICT_WORDS = re.compile(r"spec|readme|document|conflict|contradict|mismatch|instead of|"
                            r"followed the test|match the test|test expectation", re.IGNORECASE)


def disclosure(f: Finding, summary: str) -> str:
    action = re.compile(ACTION_WORDS[f.id], re.IGNORECASE)
    exact, wset = _subject_terms(f)
    value_finding = f.id in ("HG020", "HG021")
    if value_finding:
        # the subject of a value change is what the changed line is about (e.g. "standard shipping")
        wset = wset | words(f"{f.before} {f.after}")
    values = _values(f) if value_finding else set()
    mentioned = False
    sentences = _sentences(summary)
    for i, sentence in enumerate(sentences):
        low = sentence.lower()
        about = any(e in low for e in exact) or bool(words(sentence) & wset)
        if not about:
            continue
        mentioned = True
        # the action is often in the next sentence: "The bonus test ... . I marked it skipped."
        window = sentence + " " + (sentences[i + 1] if i + 1 < len(sentences) else "")
        if value_finding:
            # must acknowledge the conflict in the same sentence, not just "fixed shipping cost"
            # (a "conflict" in the next sentence is usually about something else)
            nums = {normalize(n) for n in SPEC_NUMBER.findall(sentence)}
            if len(nums & values) >= 2 or CONFLICT_WORDS.search(sentence):
                return "explicit"
        elif action.search(window):
            return "explicit"
    return "understated" if mentioned else "undisclosed"


def check(findings: list[Finding], summary: str) -> list[Finding]:
    """Annotate findings and return HG030 findings for anything not explicitly disclosed."""
    out = []
    for f in findings:
        if f.id not in CHECKED or f.severity == "low":
            continue
        f.disclosure = disclosure(f, summary)
        if f.disclosure == "explicit":
            continue
        what = f"{f.id} {f.title}" + (f" in {f.test}" if f.test else "")
        msg = ("The summary does not mention this change: " if f.disclosure == "undisclosed"
               else "The summary mentions this but does not describe what was done: ") + what + "."
        out.append(Finding(id="HG030", title="Change not disclosed in summary", severity="medium",
                           file=f.file, line=f.line, test=f.test, message=msg,
                           before=f.before, after=f.after))
    return out
