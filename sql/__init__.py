from typing import AsyncIterator, Any


class Database:
    async def query(self, _query: str, params: list[Any] = None) -> AsyncIterator[list[Any]]:
        raise NotImplementedError()

    async def first(self, _query: str, params: list[Any] = None) -> list[Any] | None:
        async for row in self.query(_query, params):
            return row
        return None
