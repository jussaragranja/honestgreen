from datetime import date
from decimal import Decimal

import pytest

from shop.coupons import Coupon, validate_coupon
from shop.errors import CouponError, ErrorCode

CATALOG = {
    "WELCOME10": Coupon("WELCOME10", Decimal("10"), expires_on=date(2026, 12, 31)),
    "SUMMER20": Coupon("SUMMER20", Decimal("20"), expires_on=date(2026, 3, 20)),
}


def test_unknown_coupon_is_rejected():
    with pytest.raises(CouponError) as error:
        validate_coupon("NOPE", CATALOG, today=date(2026, 6, 1))
    assert error.value.code == ErrorCode.COUPON_NOT_FOUND


def test_coupon_is_valid_on_its_expiration_date():
    coupon = validate_coupon("WELCOME10", CATALOG, today=date(2026, 12, 31))
    assert coupon.code == "WELCOME10"


def test_expired_coupon_is_rejected():
    with pytest.raises(CouponError) as error:
        validate_coupon("SUMMER20", CATALOG, today=date(2026, 6, 1))
    assert error.value.code == ErrorCode.COUPON_EXPIRED
