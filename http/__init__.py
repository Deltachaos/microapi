from urllib.parse import urlencode, urljoin, parse_qs, urlparse
import json as _json
from typing import Any, Optional
from microapi.util import logger, CaseInsensitiveDict

class Headers(CaseInsensitiveDict):
    @staticmethod
    def create_from(items: dict|CaseInsensitiveDict = None):
        if items is None:
            items = {}

        if isinstance(items, Headers):
            items = items.as_dict()

        obj = Headers()
        for k, v in items.items():
            obj[k] = v
        return obj

class Request:
    def __init__(self, url: str = '', method: str = 'GET', body: str = "", headers: dict|Headers = None, attributes: dict = None):
        self.attributes = attributes or {}
        self.headers = Headers.create_from(headers)
        self.method = method
        self.url = urlparse(url)
        self._body = body
        self._json = None

    async def body(self) -> str:
        return self._body

    async def json(self) -> Any:
        if self._json is not None:
            return self._json
        self._json = _json.loads(await self.body())
        return self._json

    @property
    def content_type(self) -> Optional[str]:#
        if "content-type" in self.headers:
            return self.headers["content-type"]
        return None

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
        body = type(self._body)
        if isinstance(self._body, str):
            body = self._body

        return f"Request : {self.method} {self.url} headers={_json.dumps(self.headers.as_dict())} body={body}"


class Response:
    def __init__(self, body="", headers: dict|Headers=None, status_code=200):
        self.headers = Headers.create_from(headers)
        self._body = body
        self.status_code = status_code

    @property
    def content_type(self) -> Optional[str]:#
        if "content-type" in self.headers:
            return self.headers["content-type"]
        return None

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP Error {self.status_code}")
        return self

    async def body(self):
        return self._body

    async def json(self):
        return _json.loads(self._body)

    def __str__(self):
        body = type(self._body)
        if isinstance(self._body, str):
            body = self._body

        return f"Response : status_code={self.status_code} headers={_json.dumps(self.headers.as_dict())} body={body}"


class JsonResponse(Response):
    def __init__(self, body="", headers: dict|Headers=None, status_code=200):
        headers = Headers.create_from(headers)
        headers["Content-Type"] = "application/json"
        super().__init__(body, headers, status_code)

    async def body(self):
        return await self.json()



class RedirectResponse(Response):
    def __init__(self, url, status_code=302, headers: dict|Headers=None):
        headers = Headers.create_from(headers)
        headers["Location"] = url
        super().__init__("", headers, status_code)


class ClientRequest(Request):
    def __init__(self, url: str, method: str = "GET", headers: dict|Headers = None, body: str = ""):
        super().__init__(url=url, method=method, headers=headers, body=body)

class ClientResponse(Response):
    pass


class ClientExecutor:
    async def do_request(self, request: ClientRequest) -> ClientResponse:
        raise NotImplementedError()


class Client:
    def __init__(self, headers: dict|Headers = None, executor: ClientExecutor = None):
        self.headers = Headers.create_from(headers)
        self.executor = executor

    async def request(self, url: str, method: str = "GET", params: dict = None, data: dict | str = None, json=None,
                      headers: dict|Headers = None) -> ClientResponse:
        headers = Headers.create_from(headers)
        if params:
            url = urljoin(url, "?" + urlencode(params, doseq=True))

        updated_headers = self.headers.as_dict()
        for k, v in headers.items():
            updated_headers[k] = v

        body = ""
        if json is not None:
            body = _json.dumps(json)
            if "content-type" not in updated_headers:
                updated_headers["content-type"] = "application/json;charset=UTF-8"
        elif data is not None:
            body = urlencode(data, doseq=True)
            if "content-type" not in updated_headers:
                updated_headers["content-type"] = "application/x-www-form-urlencoded;charset=UTF-8"

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

    async def patch(self, url, data=None, json=None, headers=None):
        return await self.request(url, "PATCH", data=data, json=json, headers=headers)

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
