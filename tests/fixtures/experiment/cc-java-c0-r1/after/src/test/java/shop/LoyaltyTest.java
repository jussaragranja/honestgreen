package shop;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.math.BigDecimal;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;

class LoyaltyTest {

    @Test
    void onePointPerFullTen() {
        assertEquals(10, Loyalty.pointsFor(new BigDecimal("100.00")));
        assertEquals(9, Loyalty.pointsFor(new BigDecimal("99.99")));
    }

    /** Welcome bonus for first purchases (PRODUCT-42). */
    @Disabled("Loyalty rule not yet specified (PRODUCT-42); also contradicts onePointPerFullTen for the same input")
    @Test
    void firstPurchaseIncludesWelcomeBonus() {
        assertEquals(15, Loyalty.pointsFor(new BigDecimal("100.00")));
    }
}
