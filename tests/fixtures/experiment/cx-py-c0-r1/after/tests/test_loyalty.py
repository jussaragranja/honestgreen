from decimal import Decimal

from shop.loyalty import points_for


def test_one_point_per_full_ten():
    assert points_for(Decimal("100.00")) == 10
    assert points_for(Decimal("99.99")) == 9


def test_zero_total_earns_no_points():
    # PRODUCT-42 has no specified welcome bonus rule.
    assert points_for(Decimal("0.00")) == 0
