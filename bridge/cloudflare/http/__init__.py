import json
from urllib.parse import urlunparse
from js import fetch, Response, Object
from workers import Response as CloudflareResponse, Request as CloudflareRequest

from ....bridge import RequestConverter as BridgeRequestConverter, ResponseConverter as BridgeResponseConverter
from ..util import to_py, to_js
from ....http import Request, Response, ClientRequest, ClientResponse as FrameworkClientResponse, \
    ClientExecutor as FrameworkClientExecutor, Headers


class FrameworkCloudflareRequest(Request):
    def __init__(self, _request):
        url = to_py(_request.url)
        method = to_py(_request.method)
        headers = {}
        for item in _request.headers:
            name = to_py(item)
            value = to_py(_request.headers.get(item))
            headers[name.lower()] = value

        super().__init__(url=url, method=method, headers=headers)
        self._body = None
        self._request = _request

    async def body(self):
        if self._body is not None:
            return self._body
        self._body = to_py(await self._request.text())
        return self._body


class RequestConverter(BridgeRequestConverter):
    async def to_microapi(self, _: CloudflareRequest) -> Request:
        return FrameworkCloudflareRequest(_)

    async def from_microapi(self, _: Request) -> CloudflareRequest:
        raise NotImplementedError()


class ResponseConverter(BridgeResponseConverter):
    async def to_microapi(self, _: CloudflareResponse) -> Response:
        raise NotImplementedError()

    async def from_microapi(self, _: Response) -> CloudflareResponse:
        return CloudflareResponse(await _.body(), _.status_code, headers=_.headers.as_dict())


class ClientResponse(FrameworkClientResponse):
    def __init__(self, response):
        super().__init__()
        headers = {}
        for k, v in response.headers:
            headers[to_py(k).lower()] = to_py(v)
        self.headers = Headers.create_from(headers)
        self.status_code = to_py(response.status)
        self._body = response
        self._cached = False
        self._cache_body = None

    async def json(self):
        if self._cached:
            return json.loads(self._cache_body)
        proxy = await self._body.json()
        data = to_py(proxy)
        self._cached = True
        self._cache_body = json.dumps(data)
        return data

    async def body(self):
        if self._cached:
            return self._cache_body
        proxy = await self._body.text()
        self._cached = True
        self._cache_body = to_py(proxy)
        return self._cache_body


class ClientExecutor(FrameworkClientExecutor):
    async def do_request(self, request: ClientRequest) -> FrameworkClientResponse:
        options = {
            "method": request.method,
            "headers": request.headers.as_dict()
        }

        body = await request.body()
        if body:
            options["body"] = body

        url = urlunparse(request.url)
        result = await fetch(url, to_js(options))
        return ClientResponse(result)
