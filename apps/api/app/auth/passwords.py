"""Password policy (docs/spec/09 §9.1): 10-128 chars, not common, not the email."""

from functools import lru_cache
from pathlib import Path

MIN_LENGTH = 10
MAX_LENGTH = 128

_COMMON_PASSWORDS_FILE = Path(__file__).with_name("common_passwords.txt")


@lru_cache(maxsize=1)
def _common_passwords() -> frozenset[str]:
    lines = _COMMON_PASSWORDS_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(
        line.strip().lower() for line in lines if line.strip() and not line.startswith("#")
    )


def password_problem(password: str, email: str | None = None) -> str | None:
    """Return a machine-readable reason the password is unacceptable, or None."""
    if len(password) < MIN_LENGTH:
        return "too_short"
    if len(password) > MAX_LENGTH:
        return "too_long"
    lowered = password.lower()
    if len(set(lowered)) == 1:
        return "too_common"
    if lowered in _common_passwords():
        return "too_common"
    if email and lowered == email.strip().lower():
        return "same_as_email"
    return None
