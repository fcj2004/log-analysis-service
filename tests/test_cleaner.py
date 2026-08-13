"""Log cleaner tests."""

from analyzer.cleaner import clean_line


def test_clean_valid_line():
    line = '2025-12-01T10:00:00 10.0.0.1 "GET /api/users HTTP/1.1" 200 25 "Mozilla/5.0"'
    result = clean_line(line)
    assert result is not None
    assert result[1] == "10.0.0.1"
    assert result[2] == "GET"
    assert result[3] == "/api/users"
    assert result[4] == 200
    assert result[5] == 25


def test_clean_invalid_ip():
    line = '2025-12-01T10:00:00 999.0.0.1 "GET /api/users HTTP/1.1" 200 25 "Mozilla/5.0"'
    assert clean_line(line) is None


def test_clean_invalid_status():
    line = '2025-12-01T10:00:00 10.0.0.1 "GET /api/users HTTP/1.1" 999 25 "Mozilla/5.0"'
    assert clean_line(line) is None


def test_clean_invalid_method():
    line = '2025-12-01T10:00:00 10.0.0.1 "BREW /api/users HTTP/1.1" 200 25 "Mozilla/5.0"'
    assert clean_line(line) is None


def test_clean_malformed_line():
    assert clean_line("this is not a valid log line") is None
    assert clean_line("") is None


def test_clean_space_separated_timestamp():
    line = '2025-12-01 10:00:00 10.0.0.1 "GET /api/users HTTP/1.1" 200 25 "Mozilla/5.0"'
    result = clean_line(line)
    assert result is not None
    assert result[0].strftime("%Y-%m-%d") == "2025-12-01"

