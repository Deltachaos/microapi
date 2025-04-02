from typing import Any

from microapi.bridge.cloudflare.util import to_py, to_js
from microapi.kv import Store as FrameworkStore, StoreManager as FrameworkStoreManager, StoreReference as FrameworkStoreReference

from miniapi.bridge.cloudflare import CloudContext


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

    async def list(self) -> list[str]:
        result = await self.store.list()
        return to_py(result)


class StoreReference(FrameworkStoreReference):
    def __init__(self, name: str):
        self.name = name


class StoreManager(FrameworkStoreManager):
    def __init__(self, context: CloudContext):
        self.context = context

    async def get(self, reference: StoreReference) -> Store:
        return Store(self.context.binding(reference.name))
