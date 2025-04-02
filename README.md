# miniapi
KISS python micro framework to create FaaS services on cloudflare

# Entrypoint for cloudflare

`main.py`

```python
from miniapi.bridge.cloudflare import App
from miniapi.config import FrameworkServiceProvider
from miniapi.di import tag, ServiceProvider
from miniapi.http import Response
from miniapi.router import route


@tag('controller')
class MyController:
    @route('/some/{data}')
    async def action(self, data: str):
        return Response(f"data {data}")


class AppServiceProvider(ServiceProvider):
    def services(self):
        yield MyController


def service_providers():
    yield FrameworkServiceProvider()
    yield AppServiceProvider()


app = App(service_providers=service_providers())
on_fetch = app.on_fetch()
on_scheduled = app.on_scheduled()
```

`wrangler.toml`

```ini
#:schema node_modules/wrangler/config-schema.json
name = "my-app"
main = "main.py"
compatibility_flags = ["python_workers"]
compatibility_date = "2024-10-22"
```

# Full Application example

```python
import asyncio
from urllib.parse import urlparse
from miniapi.http import Request, JsonResponse
from miniapi.kernel import HttpKernel, ViewEvent
from miniapi.config import FrameworkServiceProvider
from miniapi.di import ServiceProvider
from miniapi.di import tag
from miniapi.event import listen
from miniapi.kernel import RequestEvent
from miniapi.router import route
from miniapi.util import logger


@tag('event_subscriber')
class MyEventSubscriber:
    @listen(RequestEvent)
    def some_event(self, event: RequestEvent):
        logger(__name__).debug(f"Received {event.request.body()}")
        pass

    @listen(ViewEvent)
    def some_event(self, event: ViewEvent):
        event.response = JsonResponse(event.controller_result, status_code=400, headers={"X-Some-Header": "value"})


class MyService:
    def __init__(self, request: Request):
        self.request = request

    async def do_something(self, data):
        return f"{data} {self.request.attributes}"


@tag('controller')
class MyController:
    @route('/some/{data}')
    async def action(self, data: str, service: MyService):
        some_data = await service.do_something(data)

        return {
            "some": some_data,
            "and": "other_data"
        }


class AppServiceProvider(ServiceProvider):
    def services(self):
        yield MyController
        yield MyEventSubscriber
        yield MyService


def service_providers():
    yield FrameworkServiceProvider()
    yield AppServiceProvider()


app = HttpKernel(service_providers=service_providers())

if __name__ == '__main__':
    async def do():
        request = Request()
        request.url = urlparse("http://www.google.de/some/data")
        await app.handle(request)


    asyncio.get_event_loop().run_until_complete(do())
```