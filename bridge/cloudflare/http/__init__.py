from urllib.parse import urlunparse
from js import fetch, Headers, Response, Object
from workers import Response as CloudflareResponse, Request as CloudflareRequest

from microapi.bridge import RequestConverter as BridgeRequestConverter, ResponseConverter as BridgeResponseConverter
from microapi.bridge.cloudflare.util import to_py, to_js
from microapi.http import Request, Response, ClientRequest, ClientResponse as FrameworkClientResponse, ClientExecutor as FrameworkClientExecutor


class FrameworkCloudflareRequest(Request):
    def __init__(self, request):
        url = to_py(request.url)
        method = to_py(request.method)
        headers = {}
        for k, v in request.headers:
            headers[k.lower()] = to_py(v)

        super().__init__(url=url, method=method, headers=headers)
        self.body = None
        self._body = None
        self._request = request

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
            headers[k.lower()] = to_py(v)
        self.headers = Headers.create_from(headers)
        self.status_code = to_py(response.status)
        self._body = response

    async def json(self):
        proxy = await self._response.json()
        return to_py(proxy)

    async def body(self):
        proxy = await self._response.text()
        return to_py(proxy)


class ClientExecutor(FrameworkClientExecutor):
    async def do_request(self, request: ClientRequest) -> FrameworkClientResponse:
        options = {
            "method": request.method,
            "headers": request.headers.as_dict()
        }

        if request.body:
            options["body"] = request.body

        url = urlunparse(request.url)
        result = await fetch(url, to_js(options))
        return ClientResponse(result)
