---
name: justify-test-change
description: Write a valid justification when a test must be changed,
  disabled or deleted for a legitimate reason (the test contradicts the
  specification, a requirement changed, a feature was removed). Use whenever
  integrity-check reports a finding you classified as legitimate.
---

# Justify Test Change

## Goal
Make every intentional test change explicit, reviewable and traceable in git,
so reviewers see it in the pull request and not only in a chat message.

## A justification is valid only if it states
1. **Where**: the test file (and optionally the line).
2. **Which finding**: the finding ID from `honestgreen check` (e.g. `HG004`).
3. **Why the old test was wrong**, with evidence: a requirement, ticket, spec
   section or concrete behavior. Not "to make it pass".

## Steps
1. Gather the evidence. If there is none, the change is probably not
   legitimate: stop and report this to the user.
2. Add a trailer to the commit message, one per finding:
   ```
   Test-Change: <path>[:<line>] | <finding id> | <reason with evidence>
   ```
   Example:
   ```
   fix: apply standard shipping from the spec

   Test-Change: tests/test_shipping.py | HG004 | README section 3 sets
     standard shipping at R$ 15.00; the test expected R$ 20.00.
   ```
3. After committing, re-run `honestgreen check --base <base>` and confirm the finding
   is shown as justified. Justifications are read from commits, so uncommitted
   changes still show as unjustified.

## Rejected reasons
`honestgreen` rejects reasons shorter than 20 characters and reasons that only restate
the goal, such as "test was failing", "make tests pass", "updated test to match
implementation" or "flaky".
