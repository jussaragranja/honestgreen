package shop;

import java.time.LocalDate;
import java.util.Map;

public final class Coupons {

    private Coupons() {
    }

    /** Return the coupon if it can be used today, otherwise throw CouponException. */
    public static Coupon validate(String code, Map<String, Coupon> catalog, LocalDate today) {
        Coupon coupon = catalog.get(code);
        if (coupon == null) {
            throw new CouponException(ErrorCode.COUPON_NOT_FOUND, "coupon " + code + " not found");
        }
        if (today.isAfter(coupon.expiresOn())) {
            throw new CouponException(ErrorCode.COUPON_EXPIRED, "coupon " + code + " has expired");
        }
        return coupon;
    }
}
