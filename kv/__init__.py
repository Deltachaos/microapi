import copy
import json
from typing import Any


class Store:
    async def get(self, key: str) -> str:
        raise NotImplementedError()

    async def has(self, key: str) -> bool:
        return self.get(key) is not None

    async def put(self, key: str, value: str) -> None:
        raise NotImplementedError()

    async def delete(self, key: str) -> None:
        raise NotImplementedError()

    async def list(self, prefix: str = None):
        yield


class JSONStore:
    def __init__(self, decorated: Store):
        self.decorated = decorated

    async def get(self, key: str) -> Any:
        result = await self.decorated.get(key)
        if result is None:
            return None
        return json.loads(result)

    async def put(self, key: str, value: Any) -> None:
        await self.decorated.put(key, json.dumps(value))

    async def merge(self, key: str, value: dict) -> dict:
        result = await self.get(key)
        if result is None:
            result = {}
        value = copy.deepcopy(value)
        result = {**result, **value}
        await self.put(key, result)
        return result

    async def delete(self, key: str) -> None:
        await self.decorated.delete(key)

    async def list(self):
        async for key in self.decorated.list():
            yield key
