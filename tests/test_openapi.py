import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from irmy_common.openapi import (
    ErrorResponse, ValidationErrorResponse, configure_openapi, error_responses,
)
from irmy_common.response_codes import COMMON_CREATE_RESPONSES, COMMON_RESPONSES


def test_error_responses_have_schema_description_and_example():
    responses = error_responses(400, 401, 404, descriptions={404: "Service not found"})
    assert set(responses) == {400, 401, 404}
    assert responses[400]["model"] is ValidationErrorResponse
    assert responses[400]["content"]["application/json"]["example"]["details"]
    assert responses[401]["model"] is ErrorResponse
    assert responses[401]["description"] == "Invalid or expired token"
    assert responses[404]["description"] == "Service not found"
    assert responses[404]["content"]["application/json"]["example"] == {"error": "Service not found"}


def test_custom_400_description_is_used_as_example():
    responses = error_responses(400, descriptions={400: "applicationId is required"})
    assert responses[400]["content"]["application/json"]["example"] == {"error": "applicationId is required"}


def test_error_responses_rejects_unknown_codes():
    with pytest.raises(ValueError, match="418"):
        error_responses(418)
    with pytest.raises(ValueError, match="not in the list"):
        error_responses(401, descriptions={404: "x"})


def test_common_responses_keep_descriptions_and_get_schemas():
    assert COMMON_RESPONSES[404]["description"] == "Not found"
    assert COMMON_RESPONSES[404]["model"] is ErrorResponse
    assert COMMON_CREATE_RESPONSES[201] == {"description": "Created"}
    assert COMMON_CREATE_RESPONSES[400]["model"] is ValidationErrorResponse


class Body(BaseModel):
    name: str


def _app() -> FastAPI:
    app = FastAPI()

    @app.post("/things/{thing_id}", responses=error_responses(400, 404))
    async def create(thing_id: int, body: Body):
        return {}

    @app.get("/plain")
    async def plain():
        return {}

    return app


def test_configure_openapi_removes_422():
    app = _app()
    assert "422" in app.openapi()["paths"]["/things/{thing_id}"]["post"]["responses"]

    app = _app()
    configure_openapi(app)
    schema = app.openapi()
    responses = schema["paths"]["/things/{thing_id}"]["post"]["responses"]
    assert "422" not in responses
    assert set(responses) == {"200", "400", "404"}
    components = schema["components"]["schemas"]
    assert "HTTPValidationError" not in components and "ValidationError" not in components
    assert {"ErrorResponse", "ValidationErrorResponse", "ValidationErrorDetail", "Body"} <= set(components)
    assert app.openapi() is schema  # cached


def test_configure_openapi_keeps_a_service_model_named_validation_error():
    app = FastAPI()

    class ValidationError(BaseModel):  # a service's own model that happens to share the name
        reason: str

    @app.post("/x")
    async def x(body: Body) -> ValidationError:
        return ValidationError(reason="r")

    configure_openapi(app)
    assert "ValidationError" in app.openapi()["components"]["schemas"]
