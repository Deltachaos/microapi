import copy
import inspect

from microapi.di import tag, Container
from microapi.event import listen
from microapi.http import JsonResponse
from microapi.kernel import RequestEvent, ControllerEvent, ExceptionEvent, HttpException, ViewEvent
from microapi.router import Router
from microapi.security import Security, Firewall


@tag('event_subscriber')
class RoutingEventSubscriber:
    def __init__(self, container: Container, router: Router):
        self._container = container
        self._router = router

    @listen(RequestEvent)
    def router(self, event: RequestEvent):
        if "_controller" not in event.request.attributes:
            result = self._router.match(event.request)
            if result is not None:
                cls, method_name, params = result
                for key, value in params.items():
                    event.request.attributes[key] = copy.deepcopy(value)

                event.request.attributes["_controller"] = cls
                event.request.attributes["_controller_method"] = method_name

    @listen(ControllerEvent)
    async def controller(self, event: ControllerEvent):
        if "_controller" in event.request.attributes:
            controller_service = event.request.attributes["_controller"]
            if inspect.isclass(controller_service) and "_controller_method" in event.request.attributes:
                controller_method = event.request.attributes["_controller_method"]
                controller_service = await self._container.get(event.request.attributes["_controller"])
                method = getattr(controller_service, controller_method)
                event.controller = method
            elif callable(controller_service):
                event.controller = controller_service

    @listen(ExceptionEvent)
    async def exception(self, event: ExceptionEvent):
        if isinstance(event.exception, HttpException):
            event.response = event.exception.to_response()


@tag('event_subscriber')
class SecurityEventSubscriber:
    def __init__(self, firewall: Firewall):
        self._firewall = firewall

    @listen(RequestEvent)
    async def authenticate(self, event: RequestEvent):
        await self._firewall.authenticate(event.request)

    @listen(RequestEvent)
    async def firewall(self, event: RequestEvent):
        if not await self._firewall.is_granted(event.request):
            raise HttpException(401, f"Access denied")


@tag('event_subscriber')
class SerializeEventSubscriber:
    @listen(ViewEvent)
    async def serialize(self, event: ViewEvent):
        if event.response is None:
            event.response = JsonResponse(event.controller_result)

