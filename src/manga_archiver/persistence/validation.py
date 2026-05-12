from collections.abc import Mapping
from typing import TypeAlias

JsonObject: TypeAlias = Mapping[str, object]


def require_mapping(value: object, label: str) -> JsonObject:
    """Return a JSON object or raise for invalid persisted data."""
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")

    return value


def required_str(raw_data: JsonObject, key: str) -> str:
    """Return a required string field from a JSON object."""
    value = raw_data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")

    return value


def required_bool(raw_data: JsonObject, key: str) -> bool:
    """Return a required boolean field from a JSON object."""
    value = raw_data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")

    return value


def required_int(raw_data: JsonObject, key: str) -> int:
    """Return a required integer field from a JSON object."""
    value = raw_data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")

    return value


def required_float(raw_data: JsonObject, key: str) -> float:
    """Return a required numeric field from a JSON object as a float."""
    value = raw_data.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{key} must be a number")

    return float(value)
