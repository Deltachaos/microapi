from typing import Tuple, List, Any, AsyncIterator
import re

from ..util import to_js, to_py
from ....sql import Sqlite3Database as FrameworkDatabase


class Database(FrameworkDatabase):
    def __init__(self, connection):
        self._connection = connection

    @staticmethod
    def transform_null(sql: str, params: List[Any]) -> Tuple[str, List[Any]]:
        """
        Replaces `?` placeholders in an SQL query with `NULL` if the corresponding param is `None`,
        and returns the modified query along with the list of non-None params.

        Args:
            sql (str): The SQL query with `?` placeholders.
            params (List[Any]): The list of parameters for the placeholders.

        Returns:
            Tuple[str, List[Any]]: A tuple containing the transformed SQL query and the filtered parameter list.
        """
        param_iter = iter(params)
        transformed_params = []

        def replacer(match):
            try:
                val = next(param_iter)
            except StopIteration:
                raise ValueError("Not enough parameters for the placeholders in the query.")
            if val is None:
                return 'NULL'
            else:
                transformed_params.append(val)
                return '?'

        # Replace only the `?` that are actual placeholders (very basic regex version)
        transformed_sql = re.sub(r'\?', replacer, sql, count=len(params))

        return transformed_sql, transformed_params

    async def query(self, _query: str, params: list[Any] = None) -> AsyncIterator[list[Any]]:
        params = params or []
        _query, params = self.query_in(_query, params)
        _query, params = Database.transform_null(_query, params)
        if len(params) > 100:
            _query = self.interpolate(_query, params)
            params = []
        await self.log(_query, params)
        stmt = self._connection.prepare(to_js(_query))
        js_params = []
        for param in params:
            js_params.append(to_js(param, keep_null=True))

        if len(js_params) > 0:
            stmt = stmt.bind(*js_params)
        res = await stmt.raw()
        for row in to_py(res):
            yield row
