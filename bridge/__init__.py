from typing import Any
from microapi.http import Request, Response
from microapi.kv import Store, DatabaseStore
from microapi.queue import Queue, KVQueue
from microapi.sql import Database


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

    async def sql(self, arguments) -> Database:
        raise NotImplementedError()

    async def kv(self, arguments) -> Store:
        table = arguments["table"] if "table" in arguments else "kv"
        key_column = arguments["key_column"] if "key_column" in arguments else "_key"
        value_column = arguments["value_column"] if "value_column" in arguments else "_value"

        return DatabaseStore(await self.sql(arguments), table, key_column, value_column)

    async def queue(self, arguments) -> Queue:
        return KVQueue(await self.kv(arguments))

    async def env(self, name, default=None) -> str|None:
        raise NotImplementedError()

    async def raw(self) -> dict:
        return {}
