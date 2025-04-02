from typing import Any
from miniapi.http import Request, Response


class RequestConverter:
    async def to_miniapi(self, _: Any) -> Request:
        pass

    async def from_miniapi(self, _: Request) -> Any:
        pass


class ResponseConverter:
    async def to_miniapi(self, _: Any) -> Response:
        return Response()

    async def from_miniapi(self, _: Response) -> Any:
        pass


class CloudContext:
    def __init__(self, ):
        self.provider_name = None

    async def raw(self) -> dict:
        return {}