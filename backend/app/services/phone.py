"""Tanzanian mobile numbers, so 07xx, 2557xx and +2557xx are one customer."""

import re

_SEPARATORS = re.compile(r"[\s-]")
_MOBILE = re.compile(r"(?:\+?255|0)([67][0-9]{8})")


class InvalidPhone(ValueError):
    """Not a Tanzanian mobile number."""


def normalise_phone(raw: str) -> str:
    """Return the number as 255XXXXXXXXX."""
    match = _MOBILE.fullmatch(_SEPARATORS.sub("", raw))
    if match is None:
        raise InvalidPhone("Not a Tanzanian mobile number")
    return f"255{match.group(1)}"
