import datetime
import json
from typing import AsyncIterator, Any

from ..util import logger


class Database:
    async def log(self, _query: str, params: list[Any] = None):
        logger(__name__).info(f"Executing query: {_query} with params: {json.dumps(params)}")

    def query_in(self, sql: str, args: list[Any]):
        new_args = []
        arg_iter = iter(args)
        result_sql_parts = []
        placeholder_count = 0

        for part in sql.split('?'):
            result_sql_parts.append(part)
            try:
                arg = next(arg_iter)
            except StopIteration:
                break

            if isinstance(arg, list):
                if len(arg) == 0:
                    raise ValueError("Empty list cannot be used as SQL IN parameter")
                placeholders = ', '.join(['?'] * len(arg))
                result_sql_parts.append(f'({placeholders})')
                new_args.extend(arg)
            else:
                result_sql_parts.append('?')
                new_args.append(arg)

            placeholder_count += 1

        final_sql = ''.join(result_sql_parts)

        # optional: verify all arguments were consumed
        if next(arg_iter, None) is not None:
            raise ValueError("More arguments provided than placeholders")

        return final_sql, new_args

    def escape(self, value):
        if value is None:
            return 'NULL'
        if isinstance(value, str):
            # Escape single quotes by doubling them
            return "'" + value.replace("'", "''") + "'"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (datetime.datetime, datetime.date)):
            return "'" + value.isoformat() + "'"
        raise TypeError(f"Unsupported type: {type(value)}")

    def interpolate(self, sql: str, args: list[Any]):
        parts = sql.split('?')
        if len(parts) - 1 != len(args):
            raise ValueError("Number of placeholders does not match number of arguments")

        interpolated = []
        for i, part in enumerate(parts[:-1]):
            interpolated.append(part)
            interpolated.append(self.escape(args[i]))
        interpolated.append(parts[-1])

        return ''.join(interpolated)

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
