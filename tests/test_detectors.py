from honestgreen.detectors import compare_file

PY_BEFORE = '''
import pytest

def test_total():
    assert total(166.65) == 149.99
    assert total(0) == 0

def test_expired():
    with pytest.raises(CouponError):
        validate("OLD")

def test_bonus():
    assert points(100) == 15
'''


def ids(findings):
    return sorted(f.id for f in findings)


def check(before, after, path="tests/test_x.py", prod=True):
    return compare_file(before, after, path, path, prod)[0]


def test_identical_file_has_no_findings():
    assert check(PY_BEFORE, PY_BEFORE) == []


def test_formatting_only_change_has_no_findings():
    after = PY_BEFORE.replace("assert total(0) == 0", "assert total( 0 )==0")
    assert check(PY_BEFORE, after) == []


def test_adding_assertions_and_tests_has_no_findings():
    after = PY_BEFORE + "\n\ndef test_new():\n    assert 1 == 1\n"
    after = after.replace("assert total(0) == 0", "assert total(0) == 0\n    assert total(1) == 0.9")
    assert check(PY_BEFORE, after) == []


def test_tig001_assertion_removed():
    after = PY_BEFORE.replace("    assert total(0) == 0\n", "")
    [f] = check(PY_BEFORE, after)
    assert f.id == "HG001" and f.severity == "high" and f.test == "test_total"
    assert f.before == "assert total(0) == 0"


def test_tig002_skip_added():
    after = PY_BEFORE.replace("def test_bonus", '@pytest.mark.skip(reason="later")\ndef test_bonus')
    [f] = check(PY_BEFORE, after)
    assert f.id == "HG002" and "later" in f.after


def test_tig002_xfail_and_runtime_skip():
    after = PY_BEFORE.replace("def test_bonus():\n", "def test_bonus():\n    pytest.skip('no')\n")
    assert ids(check(PY_BEFORE, after)) == ["HG002"]


def test_tig003_weakened():
    after = PY_BEFORE.replace("assert total(166.65) == 149.99", "assert total(166.65) is not None")
    [f] = check(PY_BEFORE, after)
    assert f.id == "HG003"


def test_tig004_expected_value_changed_high_when_production_changed():
    after = PY_BEFORE.replace("== 149.99", "== 149.98")
    [f] = check(PY_BEFORE, after, prod=True)
    assert f.id == "HG004" and f.severity == "high"
    [f] = check(PY_BEFORE, after, prod=False)
    assert f.severity == "medium"


def test_tig005_deleted():
    after = PY_BEFORE.replace("def test_bonus():\n    assert points(100) == 15\n", "")
    [f] = check(PY_BEFORE, after)
    assert f.id == "HG005" and f.severity == "high" and f.test == "test_bonus"


def test_tig005_file_deleted():
    findings = compare_file(PY_BEFORE, None, "tests/test_x.py", "tests/test_x.py", True)[0]
    assert ids(findings) == ["HG005", "HG005", "HG005"]
    assert all("file removed" in f.message for f in findings)


def test_rename_without_changes_is_low():
    after = PY_BEFORE.replace("def test_bonus", "def test_loyalty_bonus")
    [f] = check(PY_BEFORE, after)
    assert f.id == "HG005" and f.severity == "low"


def test_rename_with_inverted_assertion():
    after = PY_BEFORE.replace("def test_bonus():\n    assert points(100) == 15",
                              "def test_no_bonus_yet():\n    assert points(100) == 10")
    findings = check(PY_BEFORE, after)
    assert ids(findings) == ["HG004", "HG005"]
    assert any("renamed from test_bonus" in f.test for f in findings)


JAVA_BEFORE = '''
class ShippingTest {
    @Test
    void freeAtThreshold() {
        assertEquals(new BigDecimal("0.00"), Shipping.cost(new BigDecimal("200.00")));
    }

    @Test
    void standard() {
        assertEquals(new BigDecimal("15.00"), Shipping.cost(new BigDecimal("50.00")));
    }
}
'''
JPATH = "src/test/java/shop/ShippingTest.java"


def test_java_weakened_to_not_null():
    after = JAVA_BEFORE.replace(
        'assertEquals(new BigDecimal("0.00"), Shipping.cost(new BigDecimal("200.00")));',
        'assertNotNull(Shipping.cost(new BigDecimal("200.00")));')
    [f] = check(JAVA_BEFORE, after, JPATH)
    assert f.id == "HG003" and f.test == "ShippingTest.freeAtThreshold"


def test_java_disabled_class_level_affects_all_tests():
    after = JAVA_BEFORE.replace("class ShippingTest", "@Disabled\nclass ShippingTest")
    assert ids(check(JAVA_BEFORE, after, JPATH)) == ["HG002", "HG002"]


def test_java_expected_value_changed():
    after = JAVA_BEFORE.replace('new BigDecimal("15.00")', 'new BigDecimal("20.00")')
    [f] = check(JAVA_BEFORE, after, JPATH)
    assert f.id == "HG004" and "15.00" in f.before and "20.00" in f.after


def test_java_inputs_changed_is_medium():
    after = JAVA_BEFORE.replace('Shipping.cost(new BigDecimal("50.00"))',
                                'Shipping.cost(new BigDecimal("50.00"), Method.PROMO)')
    [f] = check(JAVA_BEFORE, after, JPATH)
    assert f.id == "HG004" and f.severity == "medium"
