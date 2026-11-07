---
name: integrity-check
description: Audit the current changes before declaring a task done — tests
  weakened, disabled, deleted or renamed; production values changed against
  the specification; the specification edited to match. Use before finishing
  any task that made failing tests pass, before opening a pull request, or
  when asked whether tests or rules were bent to get CI green.
---

# Integrity Check

## Goal
Determine whether test changes in the current work preserve the suite's
ability to detect bugs.

## Steps
1. Pick the base: the branch the work started from (usually `main`).
   If you are on that branch with uncommitted changes, use `HEAD`.
2. Run:
   ```bash
   honestgreen check --base <base> --format json
   ```
   If `honestgreen` is not installed, run `pip install honestgreen` and retry.
   If that is not possible, stop and tell the user.
3. For each finding, read `test`, `before`, `after` and `message`, and open
   the file to understand the change.
4. Classify each finding:
   - **Tampering**: the test was changed to hide a failure. Revert the test
     change and fix the production code instead.
   - **Code bent to a wrong test (HG020)**: production now contradicts the
     specification. Revert the value; the test is probably wrong — correct it
     and justify (or report it if you are not sure which one is right).
   - **Specification edited (HG021)**: never change the spec to make tests pass.
     Revert it unless the user asked for the requirement change.
   - **Legitimate**: the test contradicts the specification, or the requirement
     changed. Use the `justify-test-change` skill.
   - **Unresolvable**: tests contradict each other and nothing decides which is
     right. Restore the tests and report the conflict to the user.
   - **False positive**: the detector misread the change. Explain why.
5. Re-run `honestgreen check` after any fix.
6. Draft your final message, save it to a temporary file and run
   `honestgreen check --base <base> --claims <file>`. Every HG030 means your
   message does not describe a change you made: rewrite it so it names the
   test or value and says what you did.

## Output
A short list: finding ID, file:line, classification, action taken.
Never classify a finding as legitimate without citing the evidence.

## Do not
- Do not edit `.honestgreen.toml` to silence findings (that is itself a
  high-severity finding, HG010).
- Do not resolve a finding by deleting the test that triggered it.
- Do not describe a test change as a "fix" in your final message without
  naming the test and what changed.
