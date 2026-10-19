"""
Custom pagination classes
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class StandardPagination(PageNumberPagination):
    """Standard pagination for API responses"""
    page_size = DEFAULT_PAGE_SIZE
    page_size_query_param = 'page_size'
    max_page_size = MAX_PAGE_SIZE
    page_size_query_description = 'Number of results to return per page.'
    
    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page_size': self.get_page_size(self.request),
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'results': data
        })


class LargeResultsSetPagination(PageNumberPagination):
    """Pagination for large result sets"""
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000


class SmallResultsSetPagination(PageNumberPagination):
    """Pagination for small result sets"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50
