from typing import Any

from microapi.bridge.cloudflare.util import to_py, to_js
from microapi.kv import Store as FrameworkStore


class Store(FrameworkStore):
    store = None

    def __init__(self, store: Any):
        self.store = store

    async def get(self, key: str) -> str:
        result = await self.store.get(key)
        return to_py(result)

    async def put(self, key: str, value: str) -> None:
        await self.store.put(key, to_js(value))

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
