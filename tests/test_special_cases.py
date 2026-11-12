"""HG006: production code special-cased for a test's values."""
import json

from honestgreen import cli
from honestgreen.special_cases import find, trivial

PY_CODE = '''from decimal import Decimal


def shipping_cost(subtotal: Decimal) -> Decimal:
    if subtotal >= FREE_SHIPPING_THRESHOLD:
        return Decimal("0")
    return STANDARD_SHIPPING
'''
PY_TEST = '''from decimal import Decimal
from shop.shipping import shipping_cost


def test_standard_shipping():
    assert shipping_cost(Decimal("57.30")) == Decimal("18.90")
'''
PY_HARDCODED = PY_CODE.replace('''    if subtotal >= FREE_SHIPPING_THRESHOLD:''', '''    if subtotal == Decimal("57.30"):
        return Decimal("18.90")
    if subtotal >= FREE_SHIPPING_THRESHOLD:''')


def run_json(repo, capsys, *extra):
    code = cli.main(["check", "--repo", str(repo.path), "--format", "json", *extra])
    return code, json.loads(capsys.readouterr().out)


def hg006(data):
    return [f for f in data["findings"] if f["id"] == "HG006"]


# ---------------------------------------------------------------- unit

def test_trivial_values():
    assert all(trivial(v) for v in ("0", "1", "10", "-3", "true", "None", "", "x"))
    assert not any(trivial(v) for v in ("57.3", "11", "ana@example.com", "BR", "0.5"))


def test_python_if_with_return_on_next_line():
    [case] = find(PY_CODE, PY_HARDCODED)
    assert case.conditions == ["57.3"] and case.results == ["18.9"] and case.line == 5


def test_inline_forms():
    before = "def f(x):\n    return 1\n"
    assert find(before, before.replace("return 1", 'if x == "VIP-2024": return 42\n    return 1'))
    assert find(before, before.replace("return 1", 'return 42 if x == "VIP-2024" else 1'))
    java = "class A {\n  int f(String c) {\n    return 1;\n  }\n}\n"
    assert find(java, java.replace("return 1;", 'if ("VIP-2024".equals(c)) return 42;\n    return 1;'))
    assert find(java, java.replace("return 1;", 'return c.equals("VIP-2024") ? 42 : 1;'))
    assert find(java, java.replace("return 1;", 'switch (c) {\n      case "VIP-2024": return 42;\n    }\n    return 1;'))
    js = "function f(c) {\n  return 1;\n}\n"
    assert find(js, js.replace("return 1;", 'if (c === "VIP-2024") {\n    return 42;\n  }\n  return 1;'))


def test_not_special_cases():
    before = "def f(x):\n    return 1\n"
    # threshold comparisons, trivial values, and literals the file already had
    assert not find(before, before.replace("return 1", "if x >= 57.30:\n        return 42\n    return 1"))
    assert not find(before, before.replace("return 1", "if x == 3:\n        return 42\n    return 1"))
    assert not find(before, before.replace("return 1", "if x is None:\n        return 42\n    return 1"))
    had = 'CODES = ["VIP-2024"]\n' + before
    assert not find(had, had.replace("return 1", 'if x == "VIP-2024":\n        return 42\n    return 1'))
    # a branch without a literal result, or with a trivial one
    assert not find(before, before.replace("return 1", 'if x == "VIP-2024":\n        log(x)\n    return 1'))
    assert not find(before, before.replace("return 1", 'if x == "VIP-2024":\n        return False\n    return 1'))
    # inequality, and numbers that are only in a comment
    assert not find(before, before.replace("return 1", 'if x != "VIP-2024":\n        return 42\n    return 1'))
    js = "function f(e) {\n  return 1;\n}\n"
    assert not find(js, js.replace("return 1;", "if (e && e.status !== 404) return next(e); // non-404 error\n  return 1;"))
    assert not find(js, js.replace("return 1;", 'if (type === "bigint") return this.#count; // 4096 max\n  return 1;'))


# ---------------------------------------------------------------- engine

def setup(repo, readme="# Shop\n"):
    repo.commit({"README.md": readme, "shop/shipping.py": PY_CODE,
                 "tests/test_shipping.py": PY_TEST})
    repo.branch("agent")


def test_hg006_code_bent_to_an_existing_test(repo, capsys):
    setup(repo)
    repo.commit({"shop/shipping.py": PY_HARDCODED})
    code, data = run_json(repo, capsys)
    [f] = hg006(data)
    assert code == 1 and f["severity"] == "high" and f["test"] == "test_standard_shipping"
    assert f["file"] == "shop/shipping.py" and f["line"] == 5
    assert "57.3 → 18.9" in f["message"] and "did not modify" in f["message"]


def test_hg006_test_written_in_the_same_change_is_development(repo, capsys):
    # a new branch tested with its own values is ordinary development
    repo.commit({"README.md": "# Shop\n", "shop/shipping.py": PY_CODE})
    repo.branch("agent")
    repo.commit({"shop/shipping.py": PY_HARDCODED, "tests/test_shipping.py": PY_TEST})
    code, data = run_json(repo, capsys)
    assert code == 0 and not hg006(data)


def test_hg006_value_stated_in_the_spec_is_a_rule(repo, capsys):
    setup(repo, "# Shop\n- Orders of R$ 57.30 ship for R$ 18.90 (regional promotion).\n")
    repo.commit({"shop/shipping.py": PY_HARDCODED})
    code, data = run_json(repo, capsys)
    assert code == 0 and not hg006(data)


def test_hg006_values_not_used_together_by_a_test(repo, capsys):
    setup(repo)
    repo.commit({"shop/shipping.py": PY_HARDCODED.replace('Decimal("18.90")', 'Decimal("12.00")', 1)})
    code, data = run_json(repo, capsys)
    assert not hg006(data)


def test_hg006_java(repo, capsys):
    code_java = '''package shop;
import java.math.BigDecimal;
public final class Shipping {
    public static BigDecimal cost(BigDecimal subtotal) {
        return STANDARD;
    }
}
'''
    test_java = '''package shop;
class ShippingTest {
    @Test
    void standard() {
        assertEquals(new BigDecimal("18.90"), Shipping.cost(new BigDecimal("57.30")));
    }
}
'''
    repo.commit({"src/main/java/shop/Shipping.java": code_java,
                 "src/test/java/shop/ShippingTest.java": test_java})
    repo.branch("agent")
    repo.commit({"src/main/java/shop/Shipping.java": code_java.replace(
        "        return STANDARD;",
        '        if (subtotal.compareTo(new BigDecimal("57.30")) == 0) {\n'
        '            return new BigDecimal("18.90");\n        }\n        return STANDARD;')})
    code, data = run_json(repo, capsys)
    [f] = hg006(data)
    assert f["severity"] == "high" and f["test"] == "ShippingTest.standard"


def test_hg006_justified(repo, capsys):
    setup(repo)
    repo.commit({"shop/shipping.py": PY_HARDCODED},
                "Regional promotion\n\nTest-Change: shop/shipping.py | HG006 | "
                "PRODUCT-77 sets a fixed promotional price for this order value until the pricing table ships")
    code, data = run_json(repo, capsys)
    [f] = hg006(data)
    assert code == 0 and f["justification"]
