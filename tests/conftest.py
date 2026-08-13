"""Shared test fixtures."""

import pytest

from analyzer.cleaner import clean_line


@pytest.fixture()
def valid_lines():
    return [
        '2025-12-01T10:00:00 10.0.0.1 "GET /api/users HTTP/1.1" 200 25 "Mozilla/5.0"',
        '2025-12-01T10:00:01 10.0.0.2 "POST /api/orders HTTP/1.1" 201 180 "curl/8.0"',
        '2025-12-01T10:00:02 10.0.0.3 "GET /api/products HTTP/1.1" 404 15 "Mozilla/5.0"',
    ]

