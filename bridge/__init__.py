from typing import Any
from microapi.http import Request, Response
from microapi.kv import StoreReference


class RequestConverter:
    async def to_microapi(self, _: Any) -> Request:
        pass

    async def from_microapi(self, _: Request) -> Any:
        pass


class ResponseConverter:
    async def to_microapi(self, _: Any) -> Response:
        return Response()

    async def from_microapi(self, _: Response) -> Any:
        pass


class CloudContext:
    def __init__(self, ):
        self.provider_name = None

    async def kv_store_reference(self, arguments) -> StoreReference:
        raise NotImplementedError()

    async def env(self, name, default=None) -> str|None:
        raise NotImplementedError()

    async def raw(self) -> dict:
        return {}
