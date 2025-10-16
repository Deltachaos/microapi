from typing import Any

from ..util import to_py, to_js
from ....kv import Store as FrameworkStore, ExpiringStore as FrameworkExpiringStore

class StoreEngine:
    store = None

    def __init__(self, store: Any):
        self.store = store

    async def get(self, key: str) -> str:
        result = await self.store.get(key)
        return to_py(result)

    async def put(self, key: str, value: str, options: dict = None) -> None:
        if options is None:
            await self.store.put(key, to_js(value))
        else:
            await self.store.put(key, to_js(value), to_js(options))

    async def delete(self, key: str) -> None:
        await self.store.delete(to_js(key))

    async def list(self, prefix: str = None):
        if prefix is None:
            result = await self.store.list()
        else:
            result = await self.store.list(to_js({ prefix: prefix }))
        while result is not None:
            for key in to_py(result.keys):
                yield to_py(key["name"])
            if result.list_complete:
                result = None
            else:
                result = await self.store.list({ "cursor": result.cursor })


class Store(FrameworkStore):
    engine = None

    def __init__(self, store: Any):
        self.engine = StoreEngine(store)

    async def get(self, key: str) -> str:
        return await self.engine.get(key)

    async def put(self, key: str, value: str) -> None:
        await self.engine.put(key, value)

    async def delete(self, key: str) -> None:
        await self.engine.delete(key)

    async def list(self, prefix: str = None):
        async for item in self.engine.list(prefix):
            yield item


class ExpiringStore(FrameworkExpiringStore):
    engine = None
    ttl = None

    def __init__(self, store: Any, ttl: int = None):
        self.engine = StoreEngine(store)
        self.ttl = ttl

    async def get(self, key: str) -> str:
        return await self.engine.get(key)

    async def put(self, key: str, value: str) -> None:
        if self.ttl is None:
            await self.engine.put(key, value)
        else:
            await self.engine.put(key, value, {
                "expirationTtl": self.ttl
            })

    async def delete(self, key: str) -> None:
        await self.engine.delete(key)

    async def list(self, prefix: str = None):
        async for item in self.engine.list(prefix):
            yield item