from enum import IntEnum


class ApiResponseCodes(IntEnum):
    CREATE        = 201
    UPDATE_DELETE = 204


class ApiErrorCodes(IntEnum):
    BAD_REQUEST           = 400
    UNAUTHORIZED          = 401
    FORBIDDEN             = 403
    NOT_FOUND             = 404
    CONFLICT              = 409
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE   = 503


COMMON_RESPONSES = {
    401: {"description": "Invalid or expired token"},
    403: {"description": "Insufficient permissions"},
    404: {"description": "Not found"},
    500: {"description": "Internal server error"},
}

COMMON_CREATE_RESPONSES = {
    201: {"description": "Created"},
    400: {"description": "Validation error"},
    409: {"description": "Conflict"}
}

COMMON_UPDATE_RESPONSES = {
    204: {"description": "Success"},
    400: {"description": "Validation error"},
    404: {"description": "Not found"},
    409: {"description": "Conflict"}
}

COMMON_DELETE_RESPONSES = {
    204: {"description": "Success"},
    404: {"description": "Not found"}
}
