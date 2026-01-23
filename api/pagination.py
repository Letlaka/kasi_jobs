from rest_framework.pagination import CursorPagination, PageNumberPagination


class BoundedPageNumberPagination(PageNumberPagination):
    """PageNumber pagination with an enforced maximum page size.

    - Default `page_size` can be overridden by clients (if enabled),
      but `max_page_size` prevents excessive page sizes that cause heavy
      responses or deep paging on the DB.
    - Use `page_size_query_param` with caution in public APIs; leaving it
      enabled here to allow UI tuning but capped by `max_page_size`.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class LargeCursorPagination(CursorPagination):
    """Cursor pagination for large result sets.

    Cursor pagination is recommended for deep paging scenarios because it
    avoids expensive OFFSET scans and provides stable ordering.
    """

    page_size = 50
    ordering = "-posted_at"
