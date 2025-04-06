from microapi.bridge import CloudContext
from microapi.kv import Store as FrameworkStore


class Store(FrameworkStore):
    store = None

    def __init__(self, store: dict):
        self.store = store

    async def get(self, key: str) -> str:
        return self.store.get(key)

    async def put(self, key: str, value: str) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)

    async def list(self, prefix: str = None):
        for key in list(self.store.keys()):
            if prefix is None or key.startswith(prefix):
                yield key

class StoreManager:
    stores = {}

    @staticmethod
    async def get(reference) -> Store:
        name = reference["name"]
        if name not in StoreManager.stores:
            StoreManager.stores[name] = {}
        return Store(StoreManager.stores[name])
