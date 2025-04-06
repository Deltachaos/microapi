import sqlite3
from typing import Any, AsyncIterator
from microapi.sql import Database as FrameworkDatabase


class Database(FrameworkDatabase):
    def __init__(self, name):
        self._name = name

    def connection(self):
        return sqlite3.connect(self._name + '.sqlite')

    async def query(self, _query: str, params: list[Any] = None) -> AsyncIterator[list[Any]]:
        con = self.connection()
        params = params or []
        cur = con.cursor()
        res = cur.execute(_query, params)
        for row in res:
            yield row
        cur.close()
        con.close()

