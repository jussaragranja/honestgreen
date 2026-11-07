package shop;

import java.util.List;

public final class Pagination {

    public static final int DEFAULT_PAGE_SIZE = 10;

    private Pagination() {
    }

    public static <T> List<T> paginate(List<T> items, int page) {
        return paginate(items, page, DEFAULT_PAGE_SIZE);
    }

    /** Return the items of the given page. */
    public static <T> List<T> paginate(List<T> items, int page, int pageSize) {
        if (page < 1) {
            throw new IllegalArgumentException("page must be >= 1");
        }
        if (pageSize < 1) {
            throw new IllegalArgumentException("pageSize must be >= 1");
        }
        int start = (page - 1) * pageSize;
        if (start >= items.size()) {
            return List.of();
        }
        int end = Math.min(start + pageSize, items.size());
        return List.copyOf(items.subList(start, end));
    }
}
