package shop;

import java.math.BigDecimal;
import java.math.RoundingMode;

public final class Pricing {

    private static final BigDecimal HUNDRED = new BigDecimal("100");

    private Pricing() {
    }

    /** Apply a percentage discount to a total, rounded to cents. */
    public static BigDecimal applyDiscount(BigDecimal total, BigDecimal percent) {
        if (percent.signum() < 0 || percent.compareTo(HUNDRED) > 0) {
            throw new IllegalArgumentException("percent must be between 0 and 100");
        }
        BigDecimal discounted = total.multiply(HUNDRED.subtract(percent)).divide(HUNDRED);
        return discounted.setScale(2, RoundingMode.DOWN);
    }
}
