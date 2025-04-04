from microapi.bridge import CloudContext
from microapi.kv import Store as FrameworkStore, StoreManager as FrameworkStoreManager, StoreReference as FrameworkStoreReference


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

    async def list(self):
        for key in list(self.store.keys()):
            yield key


class StoreReference(FrameworkStoreReference):
    def __init__(self, name: str):
        self.name = name


class StoreManager(FrameworkStoreManager):
    stores = {}

    def __init__(self, context: CloudContext):
        self.context = context

    async def get(self, reference: StoreReference) -> Store:
        name = reference.name
        if name not in StoreManager.stores:
            StoreManager.stores[name] = {}
        return Store(StoreManager.stores[name])
