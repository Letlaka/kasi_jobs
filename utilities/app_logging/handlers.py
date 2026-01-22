from __future__ import annotations

import contextlib
import json
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing-only import
    import logging


class PrettyJSONArrayFileHandler(TimedRotatingFileHandler):
    """Timed rotating file handler that writes a JSON array.

    Behavior:
    - On creating a new (empty) file it writes the opening bracket and newline: ``[\n``
    - For each record, it writes the pretty-printed JSON object followed by a comma and newline
      (``json.dumps(obj, indent=4) + ',\n'``).
    - On rollover or close it finalizes the file by replacing the trailing comma with a closing
      array bracket so the file becomes valid JSON.

    Notes/Tradeoffs:
    - Appending in array form is not as efficient as NDJSON; this handler reads/writes the
      whole file on finalize to remove the last trailing comma. That is acceptable for
      development and moderate-sized logs, but not recommended for very large log files.
    - The handler keeps the same rotation semantics as ``TimedRotatingFileHandler``.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            obj = self._obj_from_record(record)
            path = Path(self.baseFilename)
            objs = self._read_existing_objects(path)
            objs.append(obj)
            text_to_write = json.dumps(objs, indent=4, ensure_ascii=False) + "\n"
            try:
                path.write_text(text_to_write, encoding="utf-8")
            except OSError:
                with self._open() as fh:
                    fh.seek(0, 2)
                    fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            self.handleError(record)

    def _obj_from_record(self, record: logging.LogRecord) -> dict[str, object]:
        """Produce a JSON-serializable object from the LogRecord.

        Prefer the formatter output when it is valid JSON; otherwise emit
        a single-field object with the formatted message.
        """
        formatted = self.format(record)
        try:
            return json.loads(formatted)
        except (json.JSONDecodeError, TypeError, ValueError):
            return {"message": formatted}

    def _read_existing_objects(self, path: Path) -> list[dict[str, object]]:
        """Return a list of objects already present in `path`.

        Attempts to parse a full JSON array first, then falls back to
        extracting individual JSON object snippets.
        """
        if not path.exists():
            return []
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return []
        if not text:
            return []

        parsed = self._try_parse_array(text)
        if parsed is not None:
            return parsed

        return self._extract_objects_from_text(text)

    def _try_parse_array(self, text: str) -> list[dict[str, object]] | None:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            return None
        return None

    def _extract_objects_from_text(self, text: str) -> list[dict[str, object]]:
        objs: list[dict[str, object]] = []
        i = 0
        n = len(text)
        while i < n:
            start = text.find("{", i)
            if start == -1:
                break
            depth = 0
            j = start
            while j < n:
                ch = text[j]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start : j + 1]
                        try:
                            o = json.loads(candidate)
                            objs.append(o)
                            i = j + 1
                            break
                        except (json.JSONDecodeError, ValueError):
                            pass
                j += 1
            else:
                break
            i = max(i, start + 1)
        return objs

    def _finalize_file(self) -> None:
        """Replace the last trailing comma with a closing array bracket to make JSON valid."""
        path = Path(self.baseFilename)
        if not path.exists():
            return
        try:
            content = path.read_text(encoding="utf-8")
            if not content:
                return
            tail = content.rstrip()
            if tail.endswith("]"):
                return
            new = content.rstrip()
            if new.endswith(","):
                new = new[:-1]
            new = new.rstrip() + "\n]\n"
            path.write_text(new, encoding="utf-8")
        except (OSError, ValueError):
            return

    def doRollover(self) -> None:  # noqa: N802 - overrides logging handler method
        with contextlib.suppress(Exception):
            self._finalize_file()
        super().doRollover()
        with contextlib.suppress(OSError, ValueError):
            path = Path(self.baseFilename)
            if not path.exists() or path.stat().st_size == 0:
                with self._open() as s:
                    s.write("[\n")

    def close(self) -> None:
        try:
            self._finalize_file()
        finally:
            super().close()
