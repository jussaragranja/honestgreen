package shop;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Map;
import org.junit.jupiter.api.Test;

class CouponsTest {

    private static final Map<String, Coupon> CATALOG = Map.of(
            "WELCOME10", new Coupon("WELCOME10", new BigDecimal("10"), LocalDate.of(2026, 12, 31)),
            "SUMMER20", new Coupon("SUMMER20", new BigDecimal("20"), LocalDate.of(2026, 3, 20)));

    @Test
    void unknownCouponIsRejected() {
        CouponException error = assertThrows(CouponException.class,
                () -> Coupons.validate("NOPE", CATALOG, LocalDate.of(2026, 6, 1)));
        assertEquals(ErrorCode.COUPON_NOT_FOUND, error.getCode());
    }

    @Test
    void couponIsValidOnItsExpirationDate() {
        Coupon coupon = Coupons.validate("WELCOME10", CATALOG, LocalDate.of(2026, 12, 31));
        assertEquals("WELCOME10", coupon.code());
    }

    @Test
    void expiredCouponIsRejected() {
        CouponException error = assertThrows(CouponException.class,
                () -> Coupons.validate("SUMMER20", CATALOG, LocalDate.of(2026, 6, 1)));
        assertEquals("COUPON_EXPIRED", error.getCode().name());
    }
}
