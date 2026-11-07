package shop;

import java.math.BigDecimal;

public final class Loyalty {

    private Loyalty() {
    }

    /** Return the loyalty points earned for an order total. */
    public static int pointsFor(BigDecimal total) {
        if (total.signum() < 0) {
            throw new IllegalArgumentException("total must be >= 0");
        }
        return total.divideToIntegralValue(BigDecimal.TEN).intValue();
    }
}
