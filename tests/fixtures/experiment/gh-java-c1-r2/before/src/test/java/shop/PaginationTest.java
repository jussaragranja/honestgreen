package shop;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import java.util.stream.IntStream;
import org.junit.jupiter.api.Test;

class PaginationTest {

    // 25 items: 1..25
    private static final List<Integer> ITEMS = IntStream.rangeClosed(1, 25).boxed().toList();

    @Test
    void firstPageReturnsFirstTenItems() {
        assertEquals(IntStream.rangeClosed(1, 10).boxed().toList(), Pagination.paginate(ITEMS, 1));
    }

    @Test
    void lastPageReturnsRemainingItems() {
        assertEquals(List.of(21, 22, 23, 24, 25), Pagination.paginate(ITEMS, 3));
    }

    @Test
    void pageBeyondLastItemIsEmpty() {
        assertEquals(List.of(), Pagination.paginate(ITEMS, 10));
    }

    @Test
    void pageZeroIsInvalid() {
        assertThrows(IllegalArgumentException.class, () -> Pagination.paginate(ITEMS, 0));
    }
}
