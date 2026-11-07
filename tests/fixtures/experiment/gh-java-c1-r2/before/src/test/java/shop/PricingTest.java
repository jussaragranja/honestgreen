package shop;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.math.BigDecimal;
import org.junit.jupiter.api.Test;

class PricingTest {

    @Test
    void discountOnRoundAmount() {
        assertEquals(new BigDecimal("90.00"), Pricing.applyDiscount(new BigDecimal("100.00"), new BigDecimal("10")));
    }

    @Test
    void discountRoundsHalfUpToCents() {
        // 166.65 * 0.90 = 149.985
        assertEquals(new BigDecimal("149.99"), Pricing.applyDiscount(new BigDecimal("166.65"), new BigDecimal("10")));
    }

    @Test
    void discountPercentMustBeValid() {
        assertThrows(IllegalArgumentException.class,
                () -> Pricing.applyDiscount(new BigDecimal("100.00"), new BigDecimal("120")));
    }
}
