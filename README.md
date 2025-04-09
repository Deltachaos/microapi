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
git submodule add https://github.com/Deltachaos/microapi microapi
```

Then, you can import and use it in your Cloudflare Worker application.

## Usage

### Full Example Project

See [Deltachaos/microapi-example](https://github.com/Deltachaos/microapi-example)

### Basic Cloudflare Worker Entrypoint

This is a small example to demonstrate the basic functionality.

```python
from microapi.bridge.cloudflare import App
from microapi.config import FrameworkServiceProvider
from microapi.di import tag, ServiceProvider
from microapi.bridge import CloudContext
from microapi.kv import JSONStore
from microapi.http import Request, Response, JsonResponse
from microapi.router import route
from microapi.queue import QueueBinding, BatchMessageHandler, Queue, MessageBatch
from microapi import CloudContextQueueBindingFactory


@tag('queue')
class MyQueue(QueueBinding):
    pass


@tag("queue_message_handler")
class MyBatchHandler(BatchMessageHandler):
    async def supports(self, queue: Queue) -> bool:
        return isinstance(queue, MyQueue)

    async def handle(self, batch: MessageBatch, queue: Queue):
        async for message in batch.messages():
            data = await message.get()
            try:
                print(f"Some {data}")
                await message.ack()
            except Exception as e:
                await message.retry()

                
@tag('controller')
class MyController:
    def __init__(self, context: CloudContext):
        self.context = context

    @route('/some/{key}')
    async def action(self, request: Request, key: str):
        store = JSONStore(await self.context.kv({"name": "SOME_KV_STORE"}))

        if request.method == "POST":
            body_data = await request.json()
            # equivalent to  
            # data = json.loads(await request.body())
            await store.put(key, body_data)
            
        store_data = await store.get(key)
        return JsonResponse(store_data, status_code=201 if request.method == "POST" else 200, headers={
            "X-Some-Examle": "123"
        })

    @route('/some/{key}')
    async def queue(self, q: MyQueue):
        await q.send({
            "some": "data"
        })
        return Response(status_code=204)

    
class AppServiceProvider(ServiceProvider):
    def services(self):
        # for cloudflare queues are currently only supported by KV and Cron
        # so name is a KV store in this case
        yield MyQueue, CloudContextQueueBindingFactory.create(MyQueue, {"name": "SOME_QUEUE"})
        yield MyBatchHandler
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

This example can be run locally for testing. It does not use the cloudflare entrypoint, but instead mocks a `Request` object.

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
