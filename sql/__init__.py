import json
from typing import AsyncIterator, Any

from microapi.util import logger


class Database:
    async def log(self, _query: str, params: list[Any] = None):
        logger(__name__).debug(f"Executing query: {_query} with params: {json.dumps(params)}")

    async def query(self, _query: str, params: list[Any] = None) -> AsyncIterator[list[Any]]:
        raise NotImplementedError()

    async def first(self, _query: str, params: list[Any] = None) -> list[Any] | None:
        async for row in self.query(_query, params):
            return row
        return None

    async def execute(self, _query: str, params: list[Any] = None) -> None:
        await self.first(_query, params)

    async def insert(self, table: str, values: dict[str, Any]) -> None:
        columns = ', '.join(values.keys())
        placeholders = ', '.join(['?'] * len(values))
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        await self.execute(sql, list(values.values()))

    async def insert_replace(self, table: str, values: dict[str, Any]) -> None:
        columns = ', '.join(values.keys())
        placeholders = ', '.join(['?'] * len(values))
        sql = f"REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
        await self.execute(sql, list(values.values()))

    async def merge(self, table: str, values: dict[str, Any]) -> None:
        if not values:
            raise ValueError("Cannot merge with empty values")

        columns = ', '.join(values.keys())
        placeholders = ', '.join(['?'] * len(values))
        update_clause = ', '.join([f"{key}=excluded.{key}" for key in values.keys()])

        sql = (
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT DO UPDATE SET {update_clause}"
        )

        await self.execute(sql, list(values.values()))
