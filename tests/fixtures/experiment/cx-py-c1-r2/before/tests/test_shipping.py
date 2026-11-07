from decimal import Decimal

from shop.shipping import shipping_cost


def test_standard_shipping_cost():
    assert shipping_cost(Decimal("50.00"), "standard") == Decimal("20.00")


def test_free_shipping_above_threshold():
    assert shipping_cost(Decimal("250.00"), "standard") == Decimal("0.00")


def test_free_shipping_at_exact_threshold():
    assert shipping_cost(Decimal("200.00"), "standard") == Decimal("0.00")


def test_express_shipping_is_never_free():
    assert shipping_cost(Decimal("300.00"), "express") == Decimal("35.00")
