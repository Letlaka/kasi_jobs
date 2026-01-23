"""Merge an OpenAPI fragment into a generated schema.yml.

Usage:
  python scripts/merge_openapi.py --schema schema.yml --fragment api/error_codes_openapi.yml

This performs a deep-merge of mapping keys and writes the merged schema
back to the schema file (overwrites). Keep a backup if desired.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover - runtime helper
    logging.error("PyYAML is required: pip install pyyaml")
    raise


def deep_merge(a: dict, b: dict) -> None:
    """Merge b into a in-place, merging nested dicts.

    Lists and non-dict values are replaced by b's value.
    """
    for k, v in b.items():
        if k in a and isinstance(a[k], dict) and isinstance(v, dict):
            deep_merge(a[k], v)
        else:
            a[k] = v


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True, help="Path to generated schema.yml")
    parser.add_argument("--fragment", required=True, help="Path to fragment YAML to merge")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    schema_path = Path(args.schema)
    fragment_path = Path(args.fragment)
    if not schema_path.exists():
        logging.error("schema file not found: %s", schema_path)
        return 2
    if not fragment_path.exists():
        logging.error("fragment file not found: %s", fragment_path)
        return 2

    with schema_path.open("r", encoding="utf-8") as f:
        schema = yaml.safe_load(f) or {}
    with fragment_path.open("r", encoding="utf-8") as f:
        frag = yaml.safe_load(f) or {}

    deep_merge(schema, frag)

    # Write merged result back to schema_path
    with schema_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(schema, f, sort_keys=False)

    logging.info("Merged %s into %s", fragment_path, schema_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
