# microapi

MicroAPI is a minimalistic Python micro-framework designed to create Function-as-a-Service (FaaS) applications on Cloudflare Workers. It follows the Keep It Simple, Stupid (KISS) principle to enable lightweight, structured web applications within Cloudflare's Python environment.

## Features

- **Lightweight and Fast**: Designed specifically for Cloudflare Workers with minimal overhead.
- **Dependency Injection**: Built-in DI system to manage service dependencies efficiently.
- **Event-driven**: Supports event subscribers and listeners for better extensibility.
- **Simple Routing**: Declarative route definitions similar to FastAPI.
- **JSON Responses**: Easily return structured responses in JSON format.

## Installation

MicroAPI is designed to be used as a Git submodule in your Cloudflare Worker projects.

```sh
cd src
git submodule add https://github.com/Deltachaos/microapi microapi
```

Then, you can import and use it in your Cloudflare Worker application.

## Usage

### Basic Cloudflare Worker Entrypoint

This is a small example to demonstrate the basic functionality.

```python
from microapi.bridge.cloudflare import App
from microapi.config import FrameworkServiceProvider
from microapi.di import tag, ServiceProvider
from microapi.bridge import CloudContext
from microapi.bridge.cloudflare import CloudContext as CloudflareCloudContext
from microapi.bridge.cloudflare.util import to_py
from microapi.http import Response
from microapi.router import route

@tag('controller')
class MyController:
    def __init__(self, context: CloudflareCloudContext):
        self.context = context
    
    @route('/some/{data}')
    async def action(self, data: str):
        store = await self.context.binding("SOME_KV_STORE")
        store_data = to_py(await store.get(data))
        return Response(f"data {store_data}")

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

### `wrangler.toml` Configuration

```ini
#:schema node_modules/wrangler/config-schema.json
name = "my-app"
main = "main.py"
compatibility_flags = ["python_workers"]
compatibility_date = "2024-10-22"

kv_namespaces = [
  { binding = "SOME_KV_STORE", id = "<id>" }
]
```

## Full Application Example

This example can be run localy for testing. It does not use the cloudflare entrypoint, but instead mocks a `Request` object.

```python
import asyncio
from urllib.parse import urlparse
from microapi.http import Request, JsonResponse
from microapi.kernel import HttpKernel, ViewEvent
from microapi.config import FrameworkServiceProvider
from microapi.cron import CronEvent
from microapi.di import ServiceProvider, tag
from microapi.event import listen
from microapi.kernel import RequestEvent
from microapi.router import route
from microapi.util import logger

@tag('event_subscriber')
class MyEventSubscriber:
    def __init__(self, context: CloudContext):
        self.context = context
    
    @listen(RequestEvent)
    def some_event(self, event: RequestEvent):
        logger(__name__).debug(f"Received {event.request.body()}")

    @listen(ViewEvent)
    def some_event(self, event: ViewEvent):
        event.response = JsonResponse(event.controller_result, status_code=400, headers={"X-Some-Header": "value"})

    @listen(CronEvent)
    def on_cron(self, event: CronEvent):
        logger(__name__).info(f"Cron event")

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

## Cloudflare Worker Python Support

MicroAPI leverages Cloudflare's recent support for Python in Workers. More details can be found in the official documentation:

- [Cloudflare Workers Python Documentation](https://developers.cloudflare.com/workers/languages/python/)
- [Cloudflare Workerd GitHub Repository](https://github.com/cloudflare/workerd)

## Contributions

Contributions are welcome! Feel free to open an issue or a pull request on the GitHub repository. If you have ideas for improvements or bug fixes, we’d love to hear about them.

## License

This project is licensed under the MIT License.
