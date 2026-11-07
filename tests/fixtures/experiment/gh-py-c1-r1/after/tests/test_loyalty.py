from decimal import Decimal

from shop.loyalty import points_for


def test_one_point_per_full_ten():
    assert points_for(Decimal("100.00")) == 10
    assert points_for(Decimal("99.99")) == 9
