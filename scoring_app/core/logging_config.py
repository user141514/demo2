import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional


class JsonFormatter(logging.Formatter):
    """Custom formatter that outputs one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc)
        timestamp = ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z"
        return json.dumps(
            {
                "timestamp": timestamp,
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
            },
            ensure_ascii=False,
        )


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with a JSON formatter writing to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=[handler])


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a logger instance for the given name (defaults to __name__)."""
    return logging.getLogger(name or __name__)
