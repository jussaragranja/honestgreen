from decimal import Decimal

from shop.loyalty import points_for


def test_one_point_per_full_ten():
    assert points_for(Decimal("100.00")) == 10
    assert points_for(Decimal("99.99")) == 9


def test_first_purchase_includes_welcome_bonus():
    """Welcome bonus for first purchases (PRODUCT-42)."""
    assert points_for(Decimal("100.00")) == 15
