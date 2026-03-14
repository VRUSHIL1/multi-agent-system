from typing import Any, Dict, List, Union

from fastapi.responses import JSONResponse
from pydantic import BaseModel


class StandardResponse(BaseModel):
    status_code: int
    message: str = ""
    data: Union[List[Any], Dict[str, Any], None] = None


def success_response(
    data: Union[List[Any], Dict[str, Any], Any] = None,
    message: str = "",
    status_code: int = 200,
) -> JSONResponse:
    body = StandardResponse(
        status_code=status_code,
        message=message,
        data=data,
    )

    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(exclude_none=True),
    )


class ErrorResponse(Exception):
    def __init__(self, status_code, message):
        super().__init__()
        self.status_code = status_code
        self.message = message
