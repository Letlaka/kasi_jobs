from __future__ import annotations

import ast
import json
import logging
from datetime import UTC, datetime
from typing import Any


class SafeJSONFormatter(logging.Formatter):
    """Formatter that emits a single JSON object per log record.

    It prefers structured attributes attached to the LogRecord (e.g.
    `log_name`, `event`, `event_id`, `trace_id`, `event_uuid`, etc.) and
    falls back to a simple message object when none are present. This is a
    defensive formatter: it guarantees the output is valid JSON even when
    callers used the stdlib logging API or when messages arrive as Python
    dict string representations.
    """

    def format(self, record: logging.LogRecord) -> str:
        try:
            candidate: dict[str, Any] = {}

            for key in (
                "log_name",
                "event",
                "event_id",
                "trace_id",
                "event_uuid",
                "user",
                "service",
                "environment",
                "source",
            ):
                if hasattr(record, key):
                    candidate[key] = getattr(record, key)

            msg = record.getMessage()
            if not candidate:
                if isinstance(msg, str) and msg.startswith("{") and msg.endswith("}"):
                    try:
                        candidate = json.loads(msg)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        try:
                            candidate = dict(ast.literal_eval(msg))
                        except (ValueError, SyntaxError):
                            candidate = {"message": msg}
                else:
                    candidate = {"message": msg}
            candidate.setdefault("logger", record.name)
            candidate.setdefault("level", record.levelname)
            ts = datetime.fromtimestamp(record.created, UTC)
            ts_iso = ts.isoformat().replace("+00:00", "Z")
            candidate.setdefault("timestamp", ts_iso)

            return json.dumps(candidate, ensure_ascii=False)
        except (TypeError, ValueError, OSError):
            return super().format(record)
