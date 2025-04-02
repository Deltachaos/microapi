import json
from typing import Any, Optional
from urllib.parse import urlparse, parse_qs


class Request:
    def __init__(self):
        self.attributes = {}
        self.headers = {}
        self.method = "GET"
        self.status_code = 200
        self.url = None
        self._json = None

    async def body(self) -> str:
        return ""

    async def json(self) -> Any:
        if self._json is not None:
            return self._json
        self._json = json.loads(await self.body())
        return self._json

    @property
    def content_type(self) -> Optional[str]:
        return self.headers.get("content-type", None)

    @property
    def path(self) -> Optional[str]:
        if self.url is None:
            return None
        return self.url.path

    @property
    def query(self) -> Optional[dict]:
        if self.url is None:
            return None
        query = parse_qs(self.url.query)
        return {k: v[0] for k, v in query.items()}

    def __str__(self):
        return f"Request : {self.method} {self.url}"


class Response:
    def __init__(self, body="", headers=None, status_code=200):
        self.headers = headers or {}
        self._body = body
        self.status_code = status_code

    async def body(self):
        return self._body

    async def json(self):
        return json.dumps(self._body)

    def __str__(self):
        return f"Response : status_code={self.status_code} headers={json.dumps(self.headers)} body={json.dumps(self._body)}"


class JsonResponse(Response):
    def __init__(self, body="", headers=None, status_code=200):
        headers = headers or {}
        headers["Content-Type"] = "application/json"
        super().__init__(body, headers, status_code)

    async def body(self):
        return await self.json()
