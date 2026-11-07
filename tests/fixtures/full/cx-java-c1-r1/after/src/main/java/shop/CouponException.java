package shop;

public class CouponException extends RuntimeException {

    private final ErrorCode code;

    public CouponException(ErrorCode code, String message) {
        super(message);
        this.code = code;
    }

    public ErrorCode getCode() {
        return code;
    }
}
