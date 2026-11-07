<!-- honestgreen:start -->
## Test Integrity

Tests in this repository are a source of truth about expected behavior.
A passing test suite must mean the code is correct, not that the tests
were changed until they passed.

### Rules
1. When a test fails, assume the production code is wrong first.
   Fix the code, not the test.
2. Never disable, skip, or delete a test to make a build pass
   (`@Disabled`, `@Ignore`, `pytest.mark.skip`, `xfail`, `pytest.skip()`).
3. Never weaken an assertion, change an expected value, or widen a
   tolerance unless the test itself is demonstrably wrong.
4. Never add special-case logic in production code that only exists
   to satisfy a specific test input.
5. The specification (README, docs, API contracts) outranks the tests. Never
   change production behavior or the specification to agree with a test that
   contradicts it: the test is what is wrong. Correct the test, then use the
   `justify-test-change` skill and add a `Test-Change:` trailer to the commit.
6. If tests contradict each other and nothing decides which is right,
   leave them failing and report the conflict.

### Before finishing any task that touched test files
Run the `integrity-check` skill and resolve or justify every high-severity
finding before declaring the task complete. In your final message, name every
test you changed, disabled or deleted, and say why.
<!-- honestgreen:end -->
