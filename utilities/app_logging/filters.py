from __future__ import annotations

import json
import logging


class LogNameFilter(logging.Filter):
    """Filter log records by the `log_name` field.

    Assumes that structlog bound logger has `log_name` in its context, e.g.:

        logger = structlog.get_logger("utilities.db").bind(log_name="Application")
    """

    def __init__(self, log_name: str) -> None:
        super().__init__()
        self.log_name = log_name

    def filter(self, record: logging.LogRecord) -> bool:  # pyright: ignore[reportReturnType]
        value = getattr(record, "log_name", None)
        if value:
            return value == self.log_name
        record_name = getattr(record, "name", "") or ""
        tail = record_name.rsplit(".", 1)[-1]
        if tail.lower() == self.log_name.lower():
            return True
        try:
            msg = record.getMessage()
        except (AttributeError, TypeError, ValueError):
            return False
        try:
            parsed_obj = json.loads(msg)
            parsed = parsed_obj.get("log_name")
            return parsed == self.log_name
        except json.JSONDecodeError:
            pass

        marker = "log_name="
        idx = msg.find(marker)
        if idx == -1:
            return False
        start = idx + len(marker)
        end = start
        while end < len(msg) and not msg[end].isspace():
            end += 1
        parsed = msg[start:end].strip()
        parsed = parsed.strip("\"',.")
        return parsed == self.log_name
