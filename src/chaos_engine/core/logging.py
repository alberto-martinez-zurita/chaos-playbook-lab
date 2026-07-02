"""
Logging Setup Module - Centralized logging configuration.

Supports plain-text (console) and structured JSON (file) output.
"""
from __future__ import annotations

import json
import logging
import logging.config
from datetime import datetime, timezone
from pathlib import Path


class _JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line (structured logging)."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any extra fields passed via `logger.info("msg", extra={...})`
        for key in ("experiment_id", "failure_rate", "outcome", "duration_ms",
                     "agent_type", "error_type", "strategy", "seed"):
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def setup_logger(
    name: str | None = None,
    verbose: bool = False,
    log_dir: str = "logs",
    json_logs: bool = True,
) -> logging.Logger:
    """Configure the root logger with console + file handlers.

    Args:
        name: Logger name (also used as log-file prefix).
        verbose: If True, console shows INFO; otherwise WARNING.
        log_dir: Directory for log files.
        json_logs: If True, file handler uses structured JSON format.

    Returns:
        A named logger instance (propagates to root).
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_prefix = name if name else "system"
    log_file = str(Path(log_dir) / f"{file_prefix}_{timestamp}.log")

    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    console_level = "INFO" if verbose else "WARNING"

    file_formatter = "json_fmt" if json_logs else "file_fmt"

    config: dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "file_fmt": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "json_fmt": {
                "()": f"{__name__}._JSONFormatter",
            },
            "console_fmt": {
                "format": "%(message)s",
            },
        },
        "handlers": {
            "file_handler": {
                "class": "logging.FileHandler",
                "level": "DEBUG",
                "formatter": file_formatter,
                "filename": log_file,
                "encoding": "utf-8",
            },
            "console_handler": {
                "class": "logging.StreamHandler",
                "level": console_level,
                "formatter": "console_fmt",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": "DEBUG",
            "handlers": ["file_handler", "console_handler"],
        },
    }

    logging.config.dictConfig(config)

    if name:
        specific_logger = logging.getLogger(name)
        specific_logger.setLevel(logging.DEBUG)
        return specific_logger

    return logging.getLogger()
