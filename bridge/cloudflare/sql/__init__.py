from typing import Any, AsyncIterator

from microapi.bridge.cloudflare.util import to_js, to_py
from microapi.sql import Database as FrameworkDatabase


class Database(FrameworkDatabase):
    def __init__(self, connection):
        self._connection = connection

    async def query(self, _query: str, params: list[Any] = None) -> AsyncIterator[list[Any]]:
        params = params or []
        stmt = self._connection.prepare(to_js(_query))
        if len(params) > 0:
            stmt = stmt.bind(*params)
        res = await stmt.raw()
        for row in to_py(res):
            yield row
