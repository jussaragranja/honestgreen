from honestgreen.parsers import is_test_file, java_parser, python_parser


# ---------------------------------------------------------------- python

def test_python_finds_functions_and_class_methods():
    src = '''
import pytest

def helper():
    assert True

def test_a():
    assert f(1) == 2

class TestThing:
    def test_b(self):
        with pytest.raises(ValueError):
            f(-1)

    def not_a_test(self):
        assert False
'''
    tests = python_parser.parse(src, "tests/test_x.py")
    assert set(tests) == {"test_a", "TestThing.test_b"}
    assert tests["test_a"].assertions[0].literals == (1, 2)
    assert tests["TestThing.test_b"].assertions[0].strength == 3


def test_python_skip_markers_from_decorator_body_class_and_module():
    src = '''
import pytest
pytestmark = pytest.mark.skip(reason="module")

@pytest.mark.xfail
def test_a():
    pytest.skip("inside")
    assert 1 == 1

@pytest.mark.skip
class TestB:
    def test_b(self):
        assert x
'''
    tests = python_parser.parse(src, "t.py")
    assert any("xfail" in m for m in tests["test_a"].skip_markers)
    assert any("pytest.skip" in m for m in tests["test_a"].skip_markers)
    assert any("module" in m for m in tests["test_a"].skip_markers)
    assert any(m == "pytest.mark.skip" for m in tests["TestB.test_b"].skip_markers)


def test_python_assertion_strength():
    src = '''
def test_s(self=None):
    assert a == 1
    assert a is not None
    assert a > 1
    assert a
'''
    strengths = [a.strength for a in python_parser.parse(src, "t.py")["test_s"].assertions]
    assert strengths == [3, 1, 2, 1]


def test_python_syntax_error_returns_empty():
    assert python_parser.parse("def test_(:\n", "t.py") == {}


# ---------------------------------------------------------------- java

JAVA = '''
package shop;

import org.junit.jupiter.api.*;

class OrderTest {
    // a comment with { braces } and @Test
    private static final String S = "} not a brace @Disabled {";

    @Test
    void total() {
        assertEquals(150, order.total());
        assertNotNull(order);
    }

    @ParameterizedTest
    @ValueSource(ints = {1, 2})
    @Disabled("broken")
    void param(int x) {
        assertThat(x).isEqualTo(1);
    }

    @Nested
    @Disabled
    class Inner {
        @Test
        void inner() throws Exception {
            Assumptions.assumeTrue(false);
            assertThat(list).isNotEmpty();
        }
    }

    void helper() { assertEquals(1, 1); }
}
'''


def test_java_finds_test_methods_only():
    tests = java_parser.parse(JAVA, "src/test/java/shop/OrderTest.java")
    assert set(tests) == {"OrderTest.total", "OrderTest.param", "Inner.inner"}


def test_java_masks_strings_and_comments():
    masked = java_parser.mask('String s = "a { b"; // c }\nint x;')
    assert "{" not in masked and "}" not in masked
    assert masked.count("\n") == 1


def test_java_assertions_strength_and_literals():
    tests = java_parser.parse(JAVA, "X.java")
    total = tests["OrderTest.total"].assertions
    assert [a.strength for a in total] == [3, 1]
    assert total[0].literals == ("150",)
    assert tests["OrderTest.param"].assertions[0].strength == 3
    assert tests["Inner.inner"].assertions[0].strength == 1


def test_java_skip_markers_method_class_and_assumptions():
    tests = java_parser.parse(JAVA, "X.java")
    assert '@Disabled("broken")' in tests["OrderTest.param"].skip_markers
    assert "@Disabled" in tests["Inner.inner"].skip_markers
    assert any("assumeTrue" in m for m in tests["Inner.inner"].skip_markers)
    assert tests["OrderTest.total"].skip_markers == set()


# ---------------------------------------------------------------- files

def test_is_test_file():
    assert is_test_file("tests/test_pricing.py")
    assert is_test_file("pkg/foo_test.py")
    assert is_test_file("src/test/java/shop/PricingTest.java")
    assert is_test_file("service/src/test/java/a/B.java")
    assert not is_test_file("shop/pricing.py")
    assert not is_test_file("src/main/java/shop/Pricing.java")
    assert not is_test_file("README.md")


# ---------------------------------------------------------------- javascript / typescript

from honestgreen.parsers import js_parser
from honestgreen.detectors import compare_file

JS = r'''
import { describe, it, expect, test } from "vitest";
// it("commented out", () => {})
const pattern = /it\("not a test"\)/g;
describe("Cart", () => {
  it("adds items", () => {
    expect(cart.total()).toBe(10);
    expect(cart.items).toHaveLength(1);
  });
  describe("coupons", () => {
    test(`applies SAVE10`, async () => {
      await expect(apply("SAVE10")).resolves.toEqual({ discount: 0.1 })
      expect(() => apply("OLD")).toThrow(CouponError)
    })
  })
  it.each([[1, 2], [2, 4]])("doubles %i", (a, b) => {
    expect(double(a)).toBe(b)
  })
  it("mocha and chai", function () {
    result.should.equal(5);
    assert.strictEqual(total, 42);
  })
});
'''


def test_js_tests_and_nested_suites():
    tests = js_parser.parse(JS, "src/cart.test.ts")
    assert set(tests) == {"Cart > adds items", "Cart > coupons > applies SAVE10", "Cart > doubles %i",
                          "Cart > mocha and chai"}
    assert [a.strength for a in tests["Cart > adds items"].assertions] == [3, 3]
    coupons = tests["Cart > coupons > applies SAVE10"].assertions
    assert coupons[0].literals == ('"SAVE10"', "0.1") and coupons[1].strength == 3
    assert [a.strength for a in tests["Cart > mocha and chai"].assertions] == [3, 3]


def test_js_skip_markers():
    src = '''
describe.skip("A", () => { it("a", () => { expect(1).toBe(1) }) })
xit("b", () => {})
test.todo("c")
test.skipIf(isCI)("d", () => { expect(2).toBe(2) })
it("e", function () { this.skip() })
it("f", (ctx) => { ctx.skip() })
test.failing("g", () => { expect(3).toBe(4) })
it.only("h", () => { expect(1).toBe(1) })
'''
    tests = js_parser.parse(src, "x.test.js")
    assert tests["A > a"].skip_markers == {"describe.skip"}
    assert tests["b"].skip_markers == {"xit"}
    assert tests["c"].skip_markers == {"test.todo"}
    assert tests["d"].skip_markers == {"test.skipIf"}
    assert tests["e"].skip_markers == {"this.skip()"}
    assert tests["f"].skip_markers == {"ctx.skip()"}
    assert tests["g"].skip_markers == {"test.failing"}
    assert tests["h"].skip_markers == set()


def test_js_assertion_strength():
    src = '''
it("s", () => {
  expect(a).toEqual({ x: 1 });
  expect(a).toBeGreaterThan(1);
  expect(a).toBeTruthy();
  expect(a).not.toBe(1);
  expect(f).toThrow();
  expect(f).toThrow("expired");
  expect(a).to.deep.equal(b);
  expect(a).to.be.ok;
  assert(a);
})
'''
    strengths = [a.strength for a in js_parser.parse(src, "s.test.js")["s"].assertions]
    assert strengths == [3, 2, 1, 1, 2, 3, 3, 1, 1]


def test_js_test_file_patterns():
    for path in ("src/cart.test.ts", "web/cart.spec.tsx", "src/__tests__/cart.ts",
                 "pkg/__tests__/deep/cart.js", "test/cart.mjs", "tests/e2e/login.cts"):
        assert is_test_file(path), path
    for path in ("src/cart.ts", "types/cart.d.ts", "src/testing.js"):
        assert not is_test_file(path), path


def test_js_findings_weakened_removed_disabled():
    before = '''
describe("coupons", () => {
  it("expires", () => {
    expect(validate("OLD")).toEqual({ valid: false, reason: "COUPON_EXPIRED" });
    expect(log).toHaveBeenCalledTimes(1);
  });
  it("applies", () => {
    expect(apply(100, "SAVE10")).toBe(90);
  });
});
'''
    after = before.replace('expect(validate("OLD")).toEqual({ valid: false, reason: "COUPON_EXPIRED" });',
                           'expect(validate("OLD")).toBeDefined();')
    after = after.replace("    expect(log).toHaveBeenCalledTimes(1);\n", "")
    after = after.replace('it("applies"', 'it.skip("applies"')
    findings = compare_file(before, after, "src/coupons.test.ts", "src/coupons.test.ts", True)[0]
    assert sorted((f.id, f.test) for f in findings) == [
        ("HG001", "coupons > expires"), ("HG002", "coupons > applies"), ("HG003", "coupons > expires")]


def test_js_expected_value_changed():
    before = 'test("total", () => { expect(total(166.65)).toBe(149.99) })\n'
    after = before.replace("149.99", "150")
    [f] = compare_file(before, after, "a.test.js", "a.test.js", True)[0]
    assert f.id == "HG004" and f.severity == "high"


def test_js_supertest_expectations():
    src = '''
it("returns the user", function (done) {
  request(app)
    .get("/users/1")
    .expect("Content-Type", /json/)
    .expect(200, { id: 1 }, done);
});
'''
    [t] = js_parser.parse(src, "test/users.js").values()
    assert [(a.text, a.strength) for a in t.assertions] == [
        ('expect("Content-Type", /json/)', 2), ("expect(200, { id: 1 }, done)", 3)]
