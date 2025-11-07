import datetime
import json
from typing import AsyncIterator, Any

from ..util import logger


class Database:
    """Base database class with basic query and prepared statement functionality."""
    
    async def log(self, _query: str, params: list[Any] = None):
        logger(__name__).info(f"Executing query: {_query} with params: {json.dumps(params)}")

    def query_in(self, sql: str, args: list[Any]):
        """Expand list arguments into SQL IN clauses with proper placeholders."""
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
        """Escape a value for SQL interpolation (use prepared statements when possible)."""
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
        """Interpolate values into SQL query (use prepared statements when possible)."""
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
        """Execute a query and return an async iterator of rows."""
        raise NotImplementedError()

    async def query_dict(
        self,
        columns: list[str],
        sql: str,
        params: list[Any] = None
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Execute a custom query and yield results as async generator of dictionaries.
        Useful for complex queries that can't use find_all_iter().

        Args:
            columns: List of column names for the result set
            sql: Custom SQL query
            params: Query parameters

        Yields:
            Dictionaries with column names as keys
        """
        async for row in self.query(sql, params):
            yield dict(zip(columns, row))

    async def first(self, _query: str, params: list[Any] = None) -> list[Any] | None:
        """Execute a query and return the first row or None."""
        async for row in self.query(_query, params):
            return row
        return None

    async def execute(self, _query: str, params: list[Any] = None) -> None:
        """Execute a query without returning results."""
        await self.first(_query, params)


class Sqlite3Database(Database):
    """SQLite3 database with helper functions to reduce repeated queries in repositories."""
    
    async def insert(self, table: str, values: dict[str, Any]) -> None:
        """Insert a row into a table."""
        columns = ', '.join(values.keys())
        placeholders = ', '.join(['?'] * len(values))
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        await self.execute(sql, list(values.values()))

    async def insert_replace(self, table: str, values: dict[str, Any]) -> None:
        """Insert or replace a row in a table (SQLite REPLACE)."""
        columns = ', '.join(values.keys())
        placeholders = ', '.join(['?'] * len(values))
        sql = f"REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
        await self.execute(sql, list(values.values()))

    async def merge(self, table: str, values: dict[str, Any]) -> None:
        """Insert or update a row in a table (SQLite UPSERT)."""
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

    async def update_where(
        self,
        table: str,
        set_values: dict[str, Any],
        where_conditions: dict[str, Any],
        exclude_keys: list[str] = None
    ) -> None:
        """
        Update rows in a table with dynamic SET and WHERE clauses.
        
        Args:
            table: Table name
            set_values: Dict of columns to update
            where_conditions: Dict of WHERE conditions (all joined with AND)
            exclude_keys: List of keys to exclude from SET clause
        """
        if not set_values:
            return
        
        exclude_keys = exclude_keys or []
        
        # Build SET clause
        set_clauses = []
        set_params = []
        for key, value in set_values.items():
            if key not in exclude_keys:
                set_clauses.append(f"{key} = ?")
                set_params.append(value)
        
        if not set_clauses:
            return  # Nothing to update
        
        # Build WHERE clause
        where_clauses = []
        where_params = []
        for key, value in where_conditions.items():
            where_clauses.append(f"{key} = ?")
            where_params.append(value)
        
        if not where_clauses:
            raise ValueError("WHERE conditions required for update_where")
        
        sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)}"
        params = set_params + where_params
        
        await self.execute(sql, params)

    async def delete_where(self, table: str, where_conditions: dict[str, Any]) -> None:
        """
        Delete rows from a table with WHERE conditions.
        
        Args:
            table: Table name
            where_conditions: Dict of WHERE conditions (all joined with AND)
        """
        if not where_conditions:
            raise ValueError("WHERE conditions required for delete_where")
        
        where_clauses = []
        params = []
        for key, value in where_conditions.items():
            where_clauses.append(f"{key} = ?")
            params.append(value)
        
        sql = f"DELETE FROM {table} WHERE {' AND '.join(where_clauses)}"
        await self.execute(sql, params)

    async def find_one(
        self,
        table: str,
        columns: list[str],
        where_conditions: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Find a single row and return as dictionary.
        
        Args:
            table: Table name
            columns: List of column names to select
            where_conditions: Dict of WHERE conditions (all joined with AND)
            
        Returns:
            Dictionary with column names as keys, or None if not found
        """
        where_clauses = []
        params = []
        for key, value in where_conditions.items():
            where_clauses.append(f"{key} = ?")
            params.append(value)
        
        where_clause = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"SELECT {', '.join(columns)} FROM {table}{where_clause}"
        
        result = await self.first(sql, params)
        if result is None:
            return None
        
        return dict(zip(columns, result))

    async def find_all(
        self,
        table: str,
        columns: list[str],
        where_conditions: dict[str, Any] = None,
        order_by: str = None
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Find multiple rows and yield as async generator of dictionaries.
        
        Args:
            table: Table name
            columns: List of column names to select
            where_conditions: Optional dict of WHERE conditions (all joined with AND)
            order_by: Optional ORDER BY clause (e.g., "name ASC", "id DESC")
            
        Yields:
            Dictionaries with column names as keys
        """
        where_conditions = where_conditions or {}
        where_clauses = []
        params = []
        
        for key, value in where_conditions.items():
            where_clauses.append(f"{key} = ?")
            params.append(value)
        
        where_clause = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        order_clause = f" ORDER BY {order_by}" if order_by else ""
        sql = f"SELECT {', '.join(columns)} FROM {table}{where_clause}{order_clause}"
        
        async for row in self.query_dict(columns, sql, params):
            yield row
