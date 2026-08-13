"""Log line parsing and validation."""

import datetime
import ipaddress
import re

LOG_PATTERN = re.compile(
    r'^(?P<time>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?) '
    r'(?P<ip>[^ ]+) '
    r'"(?P<method>[A-Z]+) (?P<path>[^ ]+) [^"]*" '
    r'(?P<status>\d+) '
    r'(?P<response_time>\d+) '
    r'"(?P<user_agent>.*)"$'
)

VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"}


def clean_line(line):
    """
    Parse one log line and return a normalized tuple.

    Returns None when the line is malformed or contains invalid data.
    """
    match = LOG_PATTERN.match(line.strip())
    if not match:
        return None

    log_time = _parse_time(match.group("time"))
    if log_time is None:
        return None

    ip = match.group("ip")
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return None

    method = match.group("method")
    if method not in VALID_METHODS:
        return None

    status = int(match.group("status"))
    if not 100 <= status <= 599:
        return None

    response_time = int(match.group("response_time"))
    if response_time < 0 or response_time > 300_000:
        return None

    return (
        log_time,
        ip,
        method,
        match.group("path"),
        status,
        response_time,
        match.group("user_agent"),
    )


def _parse_time(value):
    """Parse ISO-ish timestamp and return a datetime object."""
    # Accept both space and 'T' separators, with optional fractional seconds.
    value = value.replace("T", " ")
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            return None


def clean_file(file_path):
    """Yield normalized tuples from a log file, skipping invalid lines."""
    valid = 0
    invalid = 0
    with open(file_path, "r", encoding="utf-8") as log_file:
        for line in log_file:
            cleaned = clean_line(line)
            if cleaned is None:
                invalid += 1
                continue
            valid += 1
            yield cleaned
    return None


class CleaningStats:
    """Track valid/invalid counts while streaming."""

    def __init__(self):
        self.valid = 0
        self.invalid = 0
