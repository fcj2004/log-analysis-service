"""Database connection management with pooling."""

from dbutils.pooled_db import PooledDB
import pymysql


def parse_database_url(url):
    """Parse a sqlalchemy-style URL into pymysql connection kwargs."""
    prefix = "mysql+pymysql://"
    if not url.startswith(prefix):
        raise ValueError("DATABASE_URL must start with mysql+pymysql://")

    rest = url[len(prefix):]
    credentials, host_part = rest.split("@", 1)
    username, _, password = credentials.partition(":")
    host_port, _, database = host_part.partition("/")
    host, _, port = host_port.partition(":")

    return {
        "host": host,
        "port": int(port or 3306),
        "user": username,
        "password": password,
        "database": database,
        "charset": "utf8mb4",
    }


class DatabasePool:
    """Thread-safe database connection pool."""

    def __init__(self, database_url, pool_size=8):
        kwargs = parse_database_url(database_url)
        self.pool = PooledDB(
            creator=pymysql,
            maxconnections=pool_size,
            mincached=2,
            maxcached=pool_size,
            blocking=True,
            **kwargs,
        )

    def connection(self):
        return self.pool.connection()

    def execute_batch(self, rows):
        """Insert a batch of rows using a pooled connection."""
        sql = """
            INSERT INTO access_logs
              (log_time, client_ip, request_method, api_path,
               status, response_time_ms, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        connection = self.connection()
        try:
            with connection.cursor() as cursor:
                cursor.executemany(sql, rows)
            connection.commit()
            return len(rows)
        finally:
            connection.close()

    def query_all(self, sql, params=None):
        connection = self.connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or ())
                return cursor.fetchall()
        finally:
            connection.close()

