import http.client as http_client
from ....http import ClientRequest, ClientResponse as FrameworkClientResponse, ClientExecutor as FrameworkClientExecutor

class ClientExecutor(FrameworkClientExecutor):
    async def do_request(self, request: ClientRequest) -> FrameworkClientResponse:
        url = request.url
        conn = http_client.HTTPSConnection(url.netloc) if url.scheme == "https" else http_client.HTTPConnection(
            url.netloc)

        headers = request.headers.as_dict()
        body_str = await request.body()
        body = body_str.encode("utf-8") if body_str else None

        conn.request(request.method, url.path + ("?" + url.query if url.query else ""), body, headers)
        response = conn.getresponse()

        response_body = response.read().decode("utf-8")
        response_headers = dict(response.getheaders())

        conn.close()

        return FrameworkClientResponse(body=response_body, headers=response_headers, status_code=response.status)