import copy
import json
from typing import Any

from microapi.sql import Database


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


class DatabaseStore(Store):
    def __init__(
        self,
        database: Database,
        table: str,
        key_column: str = "_key",
        value_column: str = "_value",
    ):
        self._database = database
        self._table = table
        self._key_column = key_column
        self._value_column = value_column

    async def has(self, key: str) -> bool:
        row = await self._database.first(
            f"SELECT 1 FROM {self._table} WHERE {self._key_column} = ?",
            [key]
        )
        return row is not None

    async def get(self, key: str) -> str | None:
        if not await self.has(key):
            return None
        row = await self._database.first(
            f"SELECT {self._value_column} FROM {self._table} WHERE {self._key_column} = ?",
            [key]
        )
        return row[0] if row else None

    async def put(self, key: str, value: str) -> None:
        if await self.has(key):
            await self._database.first(
                f"UPDATE {self._table} SET {self._value_column} = ? WHERE {self._key_column} = ?",
                [value, key]
            )
        else:
            await self._database.first(
                f"INSERT INTO {self._table} ({self._key_column}, {self._value_column}) VALUES (?, ?)",
                [key, value]
            )

    async def delete(self, key: str) -> None:
        await self._database.first(
            f"DELETE FROM {self._table} WHERE {self._key_column} = ?",
            [key]
        )

    async def list(self, prefix: str = None):
        if prefix:
            query = f"SELECT {self._key_column} FROM {self._table} WHERE {self._key_column} LIKE ?"
            params = [prefix + '%']
        else:
            query = f"SELECT {self._key_column} FROM {self._table}"
            params = []

        async for row in self._database.query(query, params):
            yield row[0]


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
