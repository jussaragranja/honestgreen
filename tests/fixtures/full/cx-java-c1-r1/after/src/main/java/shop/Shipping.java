package shop;

import java.math.BigDecimal;

public final class Shipping {

    static final BigDecimal STANDARD_SHIPPING = new BigDecimal("20.00");
    static final BigDecimal EXPRESS_SHIPPING = new BigDecimal("35.00");
    static final BigDecimal FREE_SHIPPING_THRESHOLD = new BigDecimal("200.00");
    static final BigDecimal FREE = new BigDecimal("0.00");

    private Shipping() {
    }

    /** Return the shipping cost for an order subtotal and shipping method. */
    public static BigDecimal cost(BigDecimal subtotal, ShippingMethod method) {
        if (method == ShippingMethod.EXPRESS) {
            return EXPRESS_SHIPPING;
        }
        if (method == ShippingMethod.STANDARD && subtotal.compareTo(FREE_SHIPPING_THRESHOLD) >= 0) {
            return FREE;
        }
        return STANDARD_SHIPPING;
    }
}
