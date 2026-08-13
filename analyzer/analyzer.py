"""SQL-based analysis reports."""


DAILY_SUMMARY_SQL = """
    SELECT
      log_date,
      COUNT(*) AS requests,
      COUNT(DISTINCT client_ip) AS unique_visitors,
      SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) AS error_count,
      AVG(response_time_ms) AS avg_response_ms
    FROM access_logs
    GROUP BY log_date
    ORDER BY log_date DESC
    LIMIT 30
"""

TOP_APIS_SQL = """
    SELECT
      api_path,
      COUNT(*) AS hits,
      AVG(response_time_ms) AS avg_response_ms
    FROM access_logs
    GROUP BY api_path
    ORDER BY hits DESC
    LIMIT 10
"""

SLOW_REQUESTS_SQL = """
    SELECT
      log_time,
      api_path,
      response_time_ms,
      client_ip
    FROM access_logs
    ORDER BY response_time_ms DESC
    LIMIT 10
"""

TOP_IPS_SQL = """
    SELECT
      client_ip,
      COUNT(*) AS requests,
      SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) AS error_count
    FROM access_logs
    GROUP BY client_ip
    ORDER BY requests DESC
    LIMIT 10
"""


def run_reports(db):
    """Run all analysis reports and return a dict of results."""
    return {
        "daily_summary": db.query_all(DAILY_SUMMARY_SQL),
        "top_apis": db.query_all(TOP_APIS_SQL),
        "slow_requests": db.query_all(SLOW_REQUESTS_SQL),
        "top_ips": db.query_all(TOP_IPS_SQL),
    }

