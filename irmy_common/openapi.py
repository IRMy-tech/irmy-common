"""OpenAPI documentation helpers for IRMy FastAPI services.

Implements the platform standard "API documentation (OpenAPI)" (Confluence INF ->
Standards): error responses with a schema and an example, and no auto-generated
422 response (IRMy returns request validation errors as 400, see
`irmy_common.exceptions.register_exceptions_handler`).
"""
import json
from collections.abc import Mapping

from fastapi import FastAPI
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Body of every IRMy error response except request validation errors."""

    error: str = Field(description="Human-readable error message, without technical details",
                       examples=["Not found"])


class ValidationErrorDetail(BaseModel):
    field: str = Field(description="Name of the invalid field", examples=["name"])
    message: str = Field(description="Why the value is invalid",
                         examples=["String should have at most 128 characters"])


class ValidationErrorResponse(BaseModel):
    """Body of a 400 response. `details` is present when the request failed validation."""

    error: str = Field(description="Human-readable error message, without technical details",
                       examples=["Validation failed"])
    details: list[ValidationErrorDetail] = Field(
        default_factory=list, description="Invalid fields; present for request validation errors")


# code -> (default description, body model)
_DEFAULTS: dict[int, tuple[str, type[BaseModel]]] = {
    400: ("Validation error", ValidationErrorResponse),
    401: ("Invalid or expired token", ErrorResponse),
    403: ("Insufficient permissions", ErrorResponse),
    404: ("Not found", ErrorResponse),
    409: ("Conflict", ErrorResponse),
    500: ("Internal server error", ErrorResponse),
    502: ("Bad gateway", ErrorResponse),
    503: ("Service unavailable", ErrorResponse),
    504: ("Gateway timeout", ErrorResponse),
}

_VALIDATION_EXAMPLE = {
    "error": "Validation failed",
    "details": [{"field": "name", "message": "String should have at most 128 characters"}],
}


def error_responses(*codes: int, descriptions: Mapping[int, str] | None = None) -> dict[int, dict]:
    """`responses=` entries for the error codes an endpoint actually returns.

    Each entry has the body schema (`ErrorResponse`, or `ValidationErrorResponse`
    for 400), a description and an example. `descriptions` overrides the default
    description of a code; it is also used as the example error message.

        responses=error_responses(400, 401, 403, 409, 500,
                                  descriptions={409: "A service with this name already exists"})
    """
    descriptions = descriptions or {}
    unknown = set(descriptions) - set(codes)
    if unknown:
        raise ValueError(f"descriptions given for codes not in the list: {sorted(unknown)}")

    result: dict[int, dict] = {}
    for code in codes:
        if code not in _DEFAULTS:
            raise ValueError(f"no default error response for HTTP {code}")
        default_description, model = _DEFAULTS[code]
        description = descriptions.get(code, default_description)
        if code == 400 and code not in descriptions:
            example = _VALIDATION_EXAMPLE
        else:
            example = {"error": description}
        result[code] = {
            "model": model,
            "description": description,
            "content": {"application/json": {"example": example}},
        }
    return result


# FastAPI's own schemas for the 422 response.
_FASTAPI_422_SCHEMAS = ("HTTPValidationError", "ValidationError")
_HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def _strip_422(schema: dict) -> None:
    for path_item in schema.get("paths", {}).values():
        for method in _HTTP_METHODS:
            operation = path_item.get(method)
            if isinstance(operation, dict):
                operation.get("responses", {}).pop("422", None)

    components = schema.get("components", {}).get("schemas", {})
    for name in _FASTAPI_422_SCHEMAS:
        if name not in components:
            continue
        others = {k: v for k, v in components.items() if k != name}
        ref = f'"#/components/schemas/{name}"'
        if ref not in json.dumps(schema.get("paths", {})) and ref not in json.dumps(others):
            del components[name]


def configure_openapi(app: FastAPI) -> None:
    """Remove the auto-generated 422 response from the app's OpenAPI document.

    Call once after creating the app. The document is still generated lazily and
    cached by FastAPI.
    """
    generate = app.openapi

    def openapi() -> dict:
        if app.openapi_schema is None:
            _strip_422(generate())  # generate() fills app.openapi_schema
        return app.openapi_schema

    app.openapi = openapi
