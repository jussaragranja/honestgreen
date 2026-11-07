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
