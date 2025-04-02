from urllib.parse import urlencode, urljoin, parse_qs, urlparse
import json as _json
from typing import Any, Optional
from microapi.util import logger


class Request:
    def __init__(self):
        self.attributes = {}
        self.headers = {}
        self.method = "GET"
        self.url = None
        self._body = ""
        self._json = None

    async def body(self) -> str:
        return self._body

    async def json(self) -> Any:
        if self._json is not None:
            return self._json
        self._json = _json.loads(await self.body())
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

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP Error {self.status_code}")
        return self

    async def body(self):
        return self._body

    async def json(self):
        return _json.dumps(self._body)

    def __str__(self):
        return f"Response : status_code={self.status_code} headers={_json.dumps(self.headers)} body={_json.dumps(self._body)}"


class JsonResponse(Response):
    def __init__(self, body="", headers=None, status_code=200):
        headers = headers or {}
        headers["Content-Type"] = "application/json"
        super().__init__(body, headers, status_code)

    async def body(self):
        return await self.json()



class RedirectResponse(Response):
    def __init__(self, url, status_code=302, headers=None):
        if headers is None:
            headers = {}
        headers["Location"] = url
        super().__init__("", headers, status_code)


class ClientRequest(Request):
    def __init__(self, url: str, method: str = "GET", headers: dict = None, body: str = ""):
        super().__init__()
        self.headers = headers or {}
        self.attributes = None
        self.method = method
        self.url = urlparse(url)
        self._body = body

    async def body(self):
        return self._body

class ClientResponse(Response):
    pass


class ClientExecutor:
    async def do_request(self, request: ClientRequest) -> ClientResponse:
        raise NotImplementedError()


class Client:
    def __init__(self, headers: dict = None, executor: ClientExecutor = None):
        self.headers = headers or {}
        self.executor = executor

    async def request(self, url: str, method: str = "GET", params: dict = None, data: dict | str = None, json=None,
                      headers: dict = None) -> ClientResponse:
        if params:
            url = urljoin(url, "?" + urlencode(params, doseq=True))

        updated_headers = {**self.headers}
        updated_headers.update(headers)

        body = ""
        if json is not None:
            body = _json.dumps(json)
            updated_headers.setdefault("content-type", "application/json;charset=UTF-8")
        elif data is not None:
            body = urlencode(data, doseq=True)
            updated_headers.setdefault("content-type", "application/x-www-form-urlencoded;charset=UTF-8")

        client_request = ClientRequest(
            url,
            method,
            updated_headers,
            body
        )

        if self.executor is None:
            raise RuntimeError(f"No HTTP Request executor")

        logger(__name__).info(f"Client HTTP Request {client_request}")
        client_response = await self.executor.do_request(client_request)
        logger(__name__).info(f"Client HTTP Response {client_response}")

        return client_response

    async def get(self, url, params=None, headers=None):
        return await self.request(url, "GET", params=params, headers=headers)

    async def post(self, url, data=None, json=None, headers=None):
        return await self.request(url, "POST", data=data, json=json, headers=headers)

    async def put(self, url, data=None, json=None, headers=None):
        return await self.request(url, "PUT", data=data, json=json, headers=headers)

    async def delete(self, url, headers=None):
        return await self.request(url, "DELETE", headers=headers)

    async def head(self, url, headers=None):
        return await self.request(url, "HEAD", headers=headers)

    async def options(self, url, headers=None):
        return await self.request(url, "OPTIONS", headers=headers)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class ClientFactory:
    def __init__(self, executor: ClientExecutor = None):
        self.executor = executor

    def create(self, headers: dict = None) -> Client:
        return Client(headers, self.executor)
