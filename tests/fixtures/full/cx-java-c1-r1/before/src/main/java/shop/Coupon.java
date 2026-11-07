package shop;

import java.math.BigDecimal;
import java.time.LocalDate;

public record Coupon(String code, BigDecimal percent, LocalDate expiresOn) {
}
