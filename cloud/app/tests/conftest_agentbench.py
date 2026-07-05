import json
import sqlite3
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent / "golden"


def _load_cases(filename: str) -> list[dict]:
    with open(GOLDEN_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _memory_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _case_ids(filename: str) -> list[str]:
    return [case["name"] for case in _load_cases(filename)]


def _assert_schema(value, schema: dict, path: str = "$") -> None:
    expected_type = schema.get("type")
    if expected_type:
        assert _matches_type(value, expected_type), f"{path}: expected type {expected_type}, got {type(value).__name__}"

    if expected_type == "object":
        required = schema.get("required", [])
        for field in required:
            assert field in value, f"{path}: missing required field {field}"
        for field, child_schema in schema.get("properties", {}).items():
            if field in value:
                _assert_schema(value[field], child_schema, f"{path}.{field}")

    if expected_type == "array":
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                _assert_schema(item, item_schema, f"{path}[{index}]")


def _matches_type(value, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    raise AssertionError(f"Unsupported schema type: {expected_type}")
