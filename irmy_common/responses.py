from uuid import UUID
from typing import List
from pydantic import BaseModel
from fastapi.responses import JSONResponse, Response

from .exceptions import IrmyException, IrmyHTTPException
from .response_codes import ApiResponseCodes, ApiErrorCodes


class CreateResourceModel(BaseModel):
    id: UUID


class CreateManyResourcesModel(BaseModel):
    ids: List[UUID]


def basic_http_response(response_code: ApiResponseCodes, resource_id: UUID | None = None, many_resource_ids: List[UUID] | None = None):
    if response_code == ApiResponseCodes.CREATE:
        if not resource_id and not many_resource_ids:
            raise IrmyException("resource_id or many_resource_ids must be provided if response code is 201")
        if resource_id:
            return JSONResponse(
                status_code=response_code,
                content=CreateResourceModel(id=resource_id).model_dump(mode="json")
            )
        if many_resource_ids:
            return JSONResponse(
                status_code=response_code,
                content=CreateManyResourcesModel(ids=many_resource_ids).model_dump(mode="json")
            )
    elif response_code == ApiResponseCodes.UPDATE_DELETE:
        return Response(status_code=response_code)
    else:
        raise IrmyHTTPException(status_code=ApiErrorCodes.INTERNAL_SERVER_ERROR, message="Response code must be one of 201, 204")
