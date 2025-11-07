import sqlite3
from typing import Any, AsyncIterator
from ....sql import Sqlite3Database as FrameworkDatabase


class Database(FrameworkDatabase):
    def __init__(self, name):
        self._name = name

    def connection(self):
        conn = sqlite3.connect(self._name + '.sqlite')
        # Enable foreign key constraints for data integrity
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    async def query(self, _query: str, params: list[Any] = None) -> AsyncIterator[list[Any]]:
        con = self.connection()
        params = params or []
        _query, params = self.query_in(_query, params)
        cur = con.cursor()
        await self.log(_query, params)
        res = cur.execute(_query, params)
        for row in res:
            yield row
        cur.close()
        con.close()

    async def execute(self, _query: str, params: list[Any] = None) -> None:
        con = self.connection()
        params = params or []
        cur = con.cursor()
        await self.log(_query, params)
        cur.execute(_query, params)
        con.commit()
        cur.close()
        con.close()

