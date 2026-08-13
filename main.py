"""Command-line entry point for the log analysis service."""

import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import islice

from analyzer.cleaner import clean_file
from analyzer.analyzer import run_reports
from analyzer.db import DatabasePool
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def chunked(iterable, size):
    """Yield consecutive chunks of the given size."""
    iterator = iter(iterable)
    while True:
        chunk = list(islice(iterator, size))
        if not chunk:
            return
        yield chunk


def process_file(file_path, config):
    """Clean, batch, and insert log rows using a thread pool."""
    db = DatabasePool(config.DATABASE_URL, config.DB_POOL_SIZE)
    total_rows = 0
    total_invalid = 0

    def insert_batch(batch, batch_index):
        inserted = db.execute_batch(batch)
        return batch_index, inserted

    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        futures = []
        for index, batch in enumerate(chunked(clean_file(file_path), config.BATCH_SIZE)):
            futures.append(executor.submit(insert_batch, batch, index))

        for future in as_completed(futures):
            batch_index, inserted = future.result()
            total_rows += inserted
            if batch_index % 10 == 0:
                logger.info("Processed batch %s, cumulative rows=%s", batch_index, total_rows)

    logger.info("Inserted %s rows into access_logs", total_rows)
    return db


def main():
    parser = argparse.ArgumentParser(description="Process access logs and run reports")
    parser.add_argument("--file", required=True, help="Path to the access log file")
    args = parser.parse_args()

    config = Config()
    started = time.perf_counter()
    db = process_file(args.file, config)
    reports = run_reports(db)
    elapsed = time.perf_counter() - started

    print(f"\nDaily summary rows: {len(reports['daily_summary'])}")
    print(f"Top API rows: {len(reports['top_apis'])}")
    print(f"Slow request rows: {len(reports['slow_requests'])}")
    print(f"Top IP rows: {len(reports['top_ips'])}")
    print(f"Total elapsed: {elapsed:.2f}s")


if __name__ == "__main__":
    main()

