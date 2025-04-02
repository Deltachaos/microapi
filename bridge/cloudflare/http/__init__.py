from urllib.parse import urlparse
from workers import Response as CloudflareResponse, Request as CloudflareRequest
from miniapi.bridge import RequestConverter as BridgeRequestConverter, ResponseConverter as BridgeResponseConverter
from miniapi.bridge.cloudflare.util import to_py
from miniapi.http import Request, Response


class FrameworkCloudflareRequest(Request):
    def __init__(self, request):
        super().__init__()
        self.body = None
        self._body = None
        self._request = request
        self.method = to_py(request.method)
        self.headers = {}
        for k, v in request.headers:
            self.headers[k.lower()] = to_py(v)
        self.url = urlparse(self._request.url)

    async def body(self):
        if self._body is not None:
            return self._body
        self._body = to_py(await self._request.text())
        return self._body


class RequestConverter(BridgeRequestConverter):
    async def to_miniapi(self, _: CloudflareRequest) -> Request:
        return FrameworkCloudflareRequest(_)

    async def from_miniapi(self, _: Request) -> CloudflareRequest:
        raise NotImplementedError()


class ResponseConverter(BridgeResponseConverter):
    async def to_miniapi(self, _: CloudflareResponse) -> Response:
        raise NotImplementedError()

    async def from_miniapi(self, _: Response) -> CloudflareResponse:
        return CloudflareResponse(await _.body(), _.status_code, headers=_.headers)

