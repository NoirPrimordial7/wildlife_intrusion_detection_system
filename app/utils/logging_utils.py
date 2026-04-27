from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.utils.paths import LOGS_DIR


PHONE_RE = re.compile(r"\+[1-9]\d{7,14}")
KEY_RE = re.compile(r"(?i)(api[_-]?key|auth[_-]?token|account[_-]?sid|from[_-]?number)(['\"\s:=]+)([^,'\"\s}]+)")


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        message = PHONE_RE.sub(lambda match: _mask_phone(match.group(0)), message)
        message = KEY_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}***", message)
        record.msg = message
        record.args = ()
        return True


def _mask_phone(phone: str) -> str:
    if len(phone) <= 5:
        return "***"
    return f"{phone[:3]}...{phone[-2:]}"


def get_logger(name: str, filename: str) -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    handler = RotatingFileHandler(LOGS_DIR / filename, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_dict(logger: logging.Logger, level: int, message: str, payload: dict[str, Any]) -> None:
    logger.log(level, "%s | %s", message, payload)
