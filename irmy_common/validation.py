"""Constrained types for request models, per "User input validation" (Confluence INF).

Every string is trimmed before it is validated, so a value made of whitespace only
is empty and fails wherever a non-empty value is required. A violation is a
request validation error: 400 with `{error, details}` via
`irmy_common.exceptions.register_exceptions_handler`. The constraints show up in
the OpenAPI schema (`maxLength`, `pattern`, `maxProperties`, ...).

    class CreateServiceRequest(BaseModel):
        serviceName: name_str(128)
        serviceDescription: text_str(512) | None = None
        tags: Tags | None = None

PostgreSQL cannot store every character a JSON string can carry: NUL (`\\u0000`) and a
lone UTF-16 surrogate (`\\ud800`..`\\udfff`, which also has no UTF-8 form). `storable_text`
replaces each of them with its escape written out as text — the six characters `\\u0000` —
so the value can be saved and shows what was sent. `text_str` applies it before trimming
and the length check; `storable` applies it to a whole JSON-like value (webhook bodies,
event payloads).
"""
import re
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BeforeValidator, Field, StringConstraints

# "A-Za-z0-9_- including spaces"
NAME_PATTERN = r"^[A-Za-z0-9_\- ]+$"
# "Keys: A-Za-z0-9_-"
KEY_PATTERN = r"^[A-Za-z0-9_-]+$"

# Characters PostgreSQL cannot store in text / jsonb: NUL and UTF-16 surrogates. A valid
# surrogate pair is already one code point after JSON decoding, so any surrogate left is lone.
_UNSTORABLE = re.compile("[\x00\ud800-\udfff]")


def storable_text(value: str) -> str:
    """`value` with NUL and lone surrogates replaced by their escape as text (`\\u0000`)."""
    return _UNSTORABLE.sub(lambda m: f"\\u{ord(m.group()):04x}", value)


def storable(value: Any) -> Any:
    """`storable_text` applied to every string of a JSON-like value, dict keys included."""
    if isinstance(value, str):
        return storable_text(value)
    if isinstance(value, dict):
        return {storable(k): storable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [storable(item) for item in value]
    return value


def _storable_input(value: Any) -> Any:
    return storable_text(value) if isinstance(value, str) else value


def name_str(max_length: int) -> Any:
    """A name: letters, digits, `_`, `-` and spaces; trimmed; 1..max_length characters."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length,
                                            pattern=NAME_PATTERN)]


def text_str(max_length: int, *, required: bool = False) -> Any:
    """Free text: any characters; trimmed; up to max_length characters (and not empty if required).

    NUL and lone surrogates are stored as their escape text (`storable_text`), counted in the length."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1 if required else None,
                                            max_length=max_length),
                     BeforeValidator(_storable_input)]


def key_str(max_length: int = 64) -> Any:
    """A map key: letters, digits, `_` and `-`; trimmed; 1..max_length characters."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length,
                                            pattern=KEY_PATTERN)]


TagKey = key_str(64)
TagValue = text_str(256)

# "Tags": up to 10 entries, keys A-Za-z0-9_- up to 64, values up to 256 characters.
Tags = Annotated[dict[TagKey, TagValue], Field(max_length=10)]


def _check_time_zone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"'{value}' is not a valid IANA time zone, e.g. 'Europe/Kyiv' or 'UTC'") from None
    return value


# An IANA time zone name, e.g. "Europe/Kyiv".
TimeZoneName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
                         AfterValidator(_check_time_zone)]
