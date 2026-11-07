from enum import Enum


class ErrorCode(Enum):
    COUPON_NOT_FOUND = "COUPON_NOT_FOUND"
    COUPON_EXPIRED = "COUPON_EXPIRED"


class CouponError(Exception):
    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code
