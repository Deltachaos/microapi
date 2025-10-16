import json
from typing import Any

from ..cron import CronEvent
from ..di import Container
from ..event import Event, EventDispatcher
from ..http import Response, Request
from ..queue import QueueBatchEvent, MessageBatch
from ..util import logger


class HttpException(Exception):
    def __init__(self, message="", status_code=500, headers=None):
        self.message = message
        self.status_code = status_code
        self.headers = headers or {}

    def to_response(self):
        return Response(json.dumps({"error": self.message}), status_code=self.status_code, headers=self.headers)


class BootedEvent(Event):
    def __init__(self, kernel: 'HttpKernel'):
        super().__init__()
        self.kernel = kernel


class RequestEvent(Event):
    def __init__(self, request: Request):
        super().__init__()
        self.request = request
        self.response = None


class ControllerEvent(Event):
    def __init__(self, request: Request):
        super().__init__()
        self.request = request
        self.controller = None


class ViewEvent(Event):
    def __init__(self, request: Request, controller_result: Any):
        super().__init__()
        self.request = request
        self.controller_result = controller_result
        self.response = None


class ResponseEvent(Event):
    def __init__(self, request: Request, response: Response):
        super().__init__()
        self.request = request
        self.response = response


class ExceptionEvent(Event):
    def __init__(self, request: Request, exception: Exception):
        super().__init__()
        self.request = request
        self.exception = exception
        self.response = None


class HttpKernel:
    def __init__(
            self,
            container: Container = None,
            service_providers = None
    ):
        if service_providers is None:
            service_providers = []
        if container is None:
            container = Container()

        for service_provider in service_providers:
            container.provide(service_provider)

        self.container = container
        self.is_booted = False

    async def boot(self):
        if not self.is_booted:
            self.is_booted = True
            await (await self.container.get(EventDispatcher)).dispatch(BootedEvent(self))

    async def queue_batch(self, message_batch: MessageBatch, container_builder=None):
        await self.boot()
        container = self.container.build()
        if container_builder is not None:
            await container_builder(container)

        async def dispatch(_):
            await (await container.get(EventDispatcher)).dispatch(_)

        event = QueueBatchEvent(message_batch)
        await dispatch(event)

    async def cron(self, container_builder=None, actions=None):
        await self.boot()
        container = self.container.build()
        if container_builder is not None:
            await container_builder(container)

        async def dispatch(_):
            await (await container.get(EventDispatcher)).dispatch(_)

        event = CronEvent()
        event.actions = actions or []
        await dispatch(event)

    async def handle(self, request: Request, container_builder=None) -> Response:
        await self.boot()
        container = self.container.build()
        if container_builder is not None:
            await container_builder(container)

        request_body = await request.body()
        logger(__name__).debug(f"Handling request {request} - {request_body}")

        async def dispatch(_):
            await (await container.get(EventDispatcher)).dispatch(_)

        async def log_response(_response: Response):
            response_body = await _response.body()
            logger(__name__).debug(f"Responding with {_response} - {response_body}")

        try:
            container.set(Request, request)

            event = RequestEvent(request)
            await dispatch(event)

            if event.response:
                await log_response(event.response)
                return event.response

            controller_event = ControllerEvent(request)
            await dispatch(controller_event)

            if not callable(controller_event.controller):
                raise HttpException('Could not resolve controller', status_code=404)

            controller_result = await container.call(
                controller_event.controller,
                controller_event.request.attributes
            )

            if not isinstance(controller_result, Response):
                view_event = ViewEvent(request, controller_result)
                await dispatch(view_event)
                if view_event.response is None:
                    raise RuntimeError('Controller did not return a response object or is not convertable')
                controller_result = view_event.response

            response_event = ResponseEvent(request, controller_result)
            await dispatch(response_event)

            await log_response(response_event.response)
            return response_event.response
        except Exception as e:
            exception_event = ExceptionEvent(request, e)
            await dispatch(exception_event)
            response = exception_event.response or HttpException(str(e), status_code=500).to_response()
            await log_response(response)
            return response
