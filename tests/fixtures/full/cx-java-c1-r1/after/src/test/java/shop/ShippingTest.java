package shop;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.math.BigDecimal;
import org.junit.jupiter.api.Test;

class ShippingTest {

    @Test
    void standardShippingCost() {
        assertEquals(new BigDecimal("20.00"), Shipping.cost(new BigDecimal("50.00"), ShippingMethod.STANDARD));
    }

    @Test
    void freeShippingAboveThreshold() {
        assertEquals(new BigDecimal("0.00"), Shipping.cost(new BigDecimal("250.00"), ShippingMethod.STANDARD));
    }

    @Test
    void freeShippingAtExactThreshold() {
        assertEquals(new BigDecimal("0.00"), Shipping.cost(new BigDecimal("200.00"), ShippingMethod.STANDARD));
    }

    @Test
    void expressShippingIsNeverFree() {
        assertEquals(new BigDecimal("35.00"), Shipping.cost(new BigDecimal("300.00"), ShippingMethod.EXPRESS));
    }
}
