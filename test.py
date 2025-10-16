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

if __name__ == "__main__":
    from microapi.bridge.inmemory import App
    app = App(service_providers=service_providers())
    app.run(
        host='0.0.0.0',
        port=8000,
        cron_interval=30
    )
else:
    from microapi.bridge.cloudflare import App
    app = App(service_providers=service_providers(), free_tier=True)
    on_fetch = app.on_fetch()
    on_scheduled = app.on_scheduled()
    on_queue = app.on_queue()