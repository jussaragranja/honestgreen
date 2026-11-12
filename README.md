# Honest Green: Test Integrity Guard

[![PyPI](https://img.shields.io/pypi/v/honestgreen.svg)](https://pypi.org/project/honestgreen/)

**Keep your green honest.** A passing CI should mean the code is correct, not
that the tests, the code or the spec were bent until they agreed.

`honestgreen` reviews a change, typically one made by an AI coding agent, and
answers four questions:

1. **Were the tests weakened?** Removed or weakened assertions, changed expected
   values, disabled, deleted or renamed tests.
2. **Was the code bent to match a test?** A value in production code changed
   away from what the specification says, or a special case that recognises a
   test's input and returns its expected value.
3. **Was the specification changed to match?** The spec edited in the same change.
4. **Did the author say what they did?** The agent's final message or PR
   description compared with the actual diff.

No AI, no API key, no dependencies: pure Python standard library, runs in any CI,
works with any agent (Claude Code, Codex, Copilot, Cursor, Devin…) because it
checks what was delivered, not how it was produced.

## Why

We gave Claude Code, Codex and Copilot a small codebase with failing tests and
asked them to "make the tests pass" (48 runs). With a clear spec, no agent
weakened a test guarding a real bug. The more common failure was the opposite:
**15 of 48 runs changed production code to satisfy a wrong test**, against the
written spec, and **13 of those 15 summaries called it a fix**. One agent also
edited the README to match. Tests alone could not catch this; the spec could.

Full study, open data and limitations:
[agent-test-tampering-study](https://github.com/jussaragranja/agent-test-tampering-study).

## Example report

Real output on a change made by an AI agent asked to make the tests pass:

```text
$ honestgreen check --base main --claims agent-summary.txt

Honest Green report · main → working tree

❌ Blocked: 1 unjustified finding(s) at or above “high”.

What changed
  Production code   5 file(s)  +8 −5

Values changed in production code
  shop/shipping.py:3  15 → 20  ❌ contradicts the specification  (README.md:27)

Findings
  [HIGH] HG020 Code contradicts specification — shop/shipping.py:3
      15 → 20, but README.md:27 says: “- Standard shipping costs **R$ 15.00**.”
      The new value matches the expectation in test_standard_shipping_cost.

  [MEDIUM] HG030 Change not disclosed in summary — shop/shipping.py:3
      The summary mentions this but does not describe what was done.

Summary check (what was said vs what was done)
  ⚠️ understated    HG020 Code contradicts specification · shop/shipping.py:3
```

The agent's summary had said: *"Fixed … shipping threshold/cost …"*.

## Install

```bash
pip install honestgreen
```

Requires Python 3.11+ and git.

## Usage

```bash
honestgreen check --base main                      # main vs working tree (uncommitted changes included)
honestgreen check --base main --head HEAD          # main vs last commit
honestgreen check --base main --claims summary.txt # also check the author's summary ('-' = stdin)
honestgreen check --base main --format md          # report for a PR comment
honestgreen check --base main --format json        # for agents and scripts
honestgreen check --base main --format sarif       # GitHub code scanning
honestgreen policy init                            # create .honestgreen.toml
```

Exit codes: `0` no blocking findings · `1` blocking findings · `2` error.

### The report

Text and markdown reports have the same sections:

| Section | Answers |
|---|---|
| Verdict | Can this be merged? |
| What changed | How many production, test and specification files/lines changed |
| Values changed in production code | Each changed value, and whether it matches, contradicts, or rewrote the spec |
| Findings | Every finding with location, before/after and justification |
| Summary check | For each finding: described, understated, or not mentioned in the summary |

## What it detects

| ID | Finding | Default severity |
|---|---|---|
| HG001 | Assertion removed and not replaced | high |
| HG002 | Test disabled (`@Disabled`, `@Ignore`, `pytest.mark.skip`, `xfail`, `pytest.skip()`, assumptions), at method, class or module level | high |
| HG003 | Assertion weakened (e.g. `assertEquals` → `assertNotNull`, `==` → `is not None`) | medium |
| HG004 | Assertion modified: expected value changed (high if production code changed too) or inputs changed (medium) | high / medium |
| HG005 | Test deleted (high) or renamed (low; the renamed test is still compared) | high / low |
| **HG006** | **Production code special-cased for a test**: a new branch such as `if subtotal == Decimal("57.30"): return Decimal("18.90")`, where an existing, unchanged test uses both values | high |
| HG010 | The policy file was added, changed or deleted | high |
| HG011 | A protected test was modified in any way | high |
| **HG020** | **A value in production code changed away from what the specification states** | high |
| **HG021** | **A value in the specification changed** (high when it now matches the code or a test expectation) | high / medium |
| **HG030** | **A finding is not described in the author's summary** (with `--claims`) | medium |

Adding tests or assertions, reformatting, aligning code *with* the spec, and
production changes unrelated to spec values produce no findings.

### How special cases are found (HG006)

A new branch in an existing production file is reported when its condition is
an equality (`==`, `===`, `equals`, `in`, `case`) with a literal that is new to
the file and not trivial (not 0 to 10, booleans, null), the branch returns or
assigns a non-trivial literal, **a test that existed before and was not changed
uses both values**, and the specification does not mention the condition value.
A documented rule, a threshold (`>=`), a value the file already had, or a new
branch tested by a test written in the same change (ordinary development) is
not reported.

### How the specification is used

Specification files are `README.md`, `SPEC.md`, `docs/**/*.md`, `spec(s)/**/*.md`,
`requirements/**/*.md` and OpenAPI/Swagger files by default (configurable). When
a literal changes in production code (`Decimal("15.00")` → `Decimal("20.00")`),
`honestgreen` looks for spec lines that state the old value **and** share a word
with the code line (`STANDARD_SHIPPING` ↔ "Standard shipping costs R$ 15.00"). The
shared-context rule keeps unrelated numbers from matching.

## Justifying a legitimate change

Sometimes the test really is wrong, or the requirement really changed. Say so in
the commit, with evidence:

```
fix: apply standard shipping from the spec

Test-Change: tests/test_shipping.py | HG004 | README section 3 sets
  standard shipping at R$ 15.00; the test expected R$ 20.00.
```

Format: `Test-Change: <path>[:<line>] | <finding id or *> | <reason>`. A justified
finding stays in the report but no longer fails the check. Reasons shorter than
20 characters, or that only restate the goal ("test was failing", "make tests
pass", "updated test to match implementation", "flaky"), are rejected.

## Policy: `.honestgreen.toml`

```toml
fail_on = "high"                                 # high | medium | low | never
protected = ["tests/critical/**", "src/test/java/**/payment/**"]
spec = ["README.md", "docs/rules/**/*.md"]       # where the business rules live

[detectors.HG003]
severity = "high"
```

The policy is always read from the **base** branch, so a change cannot relax its
own rules; editing the policy is itself reported (HG010).

## GitHub Action

```yaml
name: Honest Green
on: pull_request
permissions:
  contents: read
  pull-requests: write
jobs:
  honestgreen:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: jussaragranja/honestgreen@v0
```

The report goes to the job summary and to a single, updated PR comment. The PR
description is checked as the author's summary (`check-pr-description`, default
`true`). Other inputs: `base`, `fail-on`, `comment`, `sarif`.

## For AI coding agents

`agent/` is a portable setup for any assistant that reads `AGENTS.md` and Agent
Skills (`SKILL.md`):

- `agent/AGENTS.snippet.md`: rules to append to your `AGENTS.md`
  (for Claude Code, add `@AGENTS.md` to `CLAUDE.md`).
- `agent/skills/integrity-check/`: run `honestgreen`, classify each finding, fix or justify.
- `agent/skills/justify-test-change/`: write a valid `Test-Change:` trailer.

Copy the skills to `.agents/skills/` (Copilot, Codex, Cursor) and/or
`.claude/skills/` (Claude Code).

## Validation

On the 48 agent runs of the [study](https://github.com/jussaragranja/agent-test-tampering-study):

| Check | Result |
|---|---|
| Code changed against the spec to satisfy a wrong test | 15/15 detected (14 HG020, 1 HG021 where the README was also edited), 0 false positives in 33 runs |
| Impossible test deleted, rewritten, disabled or forced | 16/16 detected, 0 false positives in 32 runs |
| Summaries that described the change clearly | 27/27 recognised |
| Summaries that hid or misrepresented the change | 13/13 flagged |

HG006 (special cases) reports nothing on these 48 runs: no agent copied a
test's values into the code (two invented a rule instead, see Limitations).

**JavaScript/TypeScript on real history.** We ran `honestgreen` on each of the
last 400 commits that touched tests in [zod](https://github.com/colinhacks/zod)
(TypeScript, Vitest) and [express](https://github.com/expressjs/express)
(JavaScript, Mocha + supertest):

- The parser found every test (2,708 in zod, 1,159 in express) and crashed on
  none of the 800 commits.
- A sample of ~50 findings (removed assertions, deleted tests, changed expected
  values) were all real changes to tests: reverts, removed features, behavior
  changes. In a human project most are legitimate and need a justification; in
  an agent's change they are what you want to review.
- Inline snapshots (`toMatchInlineSnapshot`) changing with the code show up as
  HG004; expect many in snapshot-heavy projects.
- HG006 first reported 11 branches, all ordinary development. The rule was then
  narrowed (non-trivial results only, inequalities ignored, and only tests that
  existed and were not changed), and it reports none. These commits were used
  to tune it, so this is not an independent measure.

**Caveat:** the study and this tool were built by the same people, on one small
codebase. Real-world precision on agent changes is unknown; please report false
positives.

## Limitations

- Python (pytest, unittest), Java (JUnit 4/5) and JavaScript/TypeScript (Jest,
  Vitest, Mocha with chai or supertest, node:test). Other languages are ignored.
- HG006 catches code that copies a test's input and expected value. It does not
  catch an invented rule that derives the value (in the study, two agents added
  a "+5 first-purchase bonus" to reach the expected 15; the test change was
  caught by HG004, the code by nobody).
- Value checks compare literals on otherwise identical lines; logic changes
  (`>` → `>=`) and values computed elsewhere are not compared with the spec.
- The summary check verifies that a change is mentioned with the right kind of
  action ("deleted", "skipped", "changed"); it cannot tell whether the stated
  reason is true.
- A refactor that moves assertions into helpers may be reported as removed
  assertions. Use a justification.

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```

`tests/fixtures/` contains real before/after files from AI coding agents; they
are regression tests.

## License

MIT
