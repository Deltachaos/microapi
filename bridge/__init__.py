from typing import Any
from ..http import Request, Response
from ..kv import Store, DatabaseStore, ExpiringStore
from ..queue import Queue, KVQueue
from ..sql import Database


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

    async def expiring_kv(self, arguments, ttl: int = None) -> ExpiringStore:
        kv = await self.kv(arguments)
        return ExpiringStore(kv, ttl)

    async def queue(self, arguments) -> Queue:
        return KVQueue(await self.kv(arguments))

    async def env(self, name, default=None) -> str|None:
        raise NotImplementedError()

    async def raw(self) -> dict:
        return {}
