"""Analyzer query tests using a fake database pool."""

from analyzer.analyzer import run_reports


class FakeDB:
    def __init__(self):
        self.queries = []

    def query_all(self, sql, params=None):
        self.queries.append(sql)
        return []


def test_run_reports_queries_all_tables():
    db = FakeDB()
    reports = run_reports(db)
    assert len(db.queries) == 4
    assert set(reports.keys()) == {
        "daily_summary",
        "top_apis",
        "slow_requests",
        "top_ips",
    }

