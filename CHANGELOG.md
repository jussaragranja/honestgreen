# Changelog

## 0.2.0

- **HG006 Production code special-cased for a test**: a new branch that
  recognises a test's input and returns its expected value
  (`if subtotal == Decimal("57.30"): return Decimal("18.90")`), where a test
  that existed and was not changed uses both values. Values stated in the
  specification, thresholds, values the file already had and branches tested
  by tests written in the same change are not reported.
- **JavaScript and TypeScript tests**: Jest, Vitest, Mocha (with chai and
  supertest) and node:test, in `*.test.*`, `*.spec.*`, `__tests__/` and
  `test(s)/` for `.js .jsx .mjs .cjs .ts .tsx .mts .cts`. Nested `describe`
  names, `it.each`, and skips (`it.skip`, `xit`, `describe.skip`, `test.todo`,
  `test.failing`, `test.skipIf`, `this.skip()`, `ctx.skip()`).
- The `integrity-check` skill and `AGENTS.md` snippet cover HG006 and JS skips.

## 0.1.0

First release: HG001-HG005 (tests weakened, disabled, deleted or renamed),
HG010-HG011 (policy and protected tests), HG020-HG021 (code or specification
bent to a test), HG030 (summary hides the change), GitHub Action, SARIF.
