"""Opaque keyset cursors (docs/spec/05 §5.1)."""

import base64
import binascii
import json
from typing import Any

from app.core.errors import ValidationError

MAX_CURSOR_LENGTH = 512


class InvalidCursorError(ValidationError):
    code = "INVALID_CURSOR"
    message = "Invalid pagination cursor."


def encode_cursor(key: list[Any]) -> str:
    raw = json.dumps(key, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> list[Any]:
    if len(cursor) > MAX_CURSOR_LENGTH:
        raise InvalidCursorError(details=[{"field": "cursor", "issue": "too_long"}])
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise InvalidCursorError(details=[{"field": "cursor", "issue": "malformed"}]) from None
    if not isinstance(value, list):
        raise InvalidCursorError(details=[{"field": "cursor", "issue": "malformed"}])
    return value
