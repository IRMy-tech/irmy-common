from enum import IntEnum

from .openapi import error_responses

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
    BAD_GATEWAY           = 502
    SERVICE_UNAVAILABLE   = 503
    GATEWAY_TIMEOUT       = 504


# Legacy: these may declare codes an endpoint never returns. New endpoints declare
# exactly their own codes with `irmy_common.openapi.error_responses`.
COMMON_RESPONSES = error_responses(401, 403, 404, 500)

COMMON_CREATE_RESPONSES = {
    201: {"description": "Created"},
    **error_responses(400, 409),
}

COMMON_UPDATE_RESPONSES = {
    204: {"description": "Success"},
    **error_responses(400, 404, 409),
}

COMMON_DELETE_RESPONSES = {
    204: {"description": "Success"},
    **error_responses(404),
}
