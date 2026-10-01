from typing import Any
from fastapi import HTTPException, Request, FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from .response_codes import ApiErrorCodes


class IrmyException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class IrmyHTTPException(HTTPException):
    def __init__(self, message: str, status_code: ApiErrorCodes):
        self.message = message
        self.status_code = status_code
        super().__init__(detail=message, status_code=status_code)


async def _irmy_exception_handler(request: Request, exc: Any) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


async def _http_exception_handler(request: Request, exc: Any) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


async def _validation_exception_handler(request: Request, exc: Any):
    details = []
    for err in exc.errors():
        loc = err.get("loc", ())
        field = str(loc[-1]) if loc else "unknown"
        details.append({"field": field, "message": err["msg"]})

    return JSONResponse(
        status_code=ApiErrorCodes.BAD_REQUEST,
        content={
            "error": "Validation failed",
            "details": details,
        },
    )


def register_exceptions_handler(app: FastAPI) -> None:
    app.add_exception_handler(IrmyHTTPException, _irmy_exception_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
