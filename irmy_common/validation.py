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
"""
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, Field, StringConstraints

# "A-Za-z0-9_- including spaces"
NAME_PATTERN = r"^[A-Za-z0-9_\- ]+$"
# "Keys: A-Za-z0-9_-"
KEY_PATTERN = r"^[A-Za-z0-9_-]+$"


def name_str(max_length: int) -> Any:
    """A name: letters, digits, `_`, `-` and spaces; trimmed; 1..max_length characters."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length,
                                            pattern=NAME_PATTERN)]


def text_str(max_length: int, *, required: bool = False) -> Any:
    """Free text: any characters; trimmed; up to max_length characters (and not empty if required)."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1 if required else None,
                                            max_length=max_length)]


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
