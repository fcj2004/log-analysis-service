"""Service configuration."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration loaded from environment variables."""

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:password@localhost/log_analysis",
    )
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "8"))

