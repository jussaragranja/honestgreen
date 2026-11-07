from decimal import Decimal

STANDARD_SHIPPING = Decimal("20.00")
EXPRESS_SHIPPING = Decimal("35.00")
FREE_SHIPPING_THRESHOLD = Decimal("200.00")
FREE = Decimal("0.00")


def shipping_cost(subtotal: Decimal, method: str = "standard") -> Decimal:
    """Return the shipping cost for an order subtotal and shipping method."""
    if method == "express":
        return EXPRESS_SHIPPING
    if method != "standard":
        raise ValueError(f"unknown shipping method: {method}")
    if subtotal >= FREE_SHIPPING_THRESHOLD:
        return FREE
    return STANDARD_SHIPPING
