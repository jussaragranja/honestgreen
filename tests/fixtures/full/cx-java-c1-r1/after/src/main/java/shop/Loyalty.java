package shop;

import java.math.BigDecimal;

public final class Loyalty {

    private Loyalty() {
    }

    /** Return the loyalty points earned for an order total. */
    public static int pointsFor(BigDecimal total) {
        return pointsFor(total, false);
    }

    /** Return points for an order, including the welcome bonus for a first purchase. */
    public static int pointsFor(BigDecimal total, boolean firstPurchase) {
        if (total.signum() < 0) {
            throw new IllegalArgumentException("total must be >= 0");
        }
        int points = total.divideToIntegralValue(BigDecimal.TEN).intValue();
        return points + (firstPurchase ? 5 : 0);
    }
}
